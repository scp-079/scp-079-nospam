# SCP-079-NOSPAM - Block spam in groups
# Copyright (C) 2019 SCP-079 <https://scp-079.org>
#
# This file is part of SCP-079-NOSPAM.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import pickle
from copy import deepcopy
from json import loads
from typing import Any

from pyrogram import Client, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import glovar
from .channel import ask_for_help, declare_message, get_content, get_debug_text, send_debug, share_data
from .etc import code, crypt_str, general_link, get_int, get_now, get_report_record, get_stripped_link, get_text
from .etc import thread, user_mention
from .file import crypt_file, data_to_file, delete_file, get_new_path, get_downloaded_path, save
from .filters import is_avatar_image, is_bad_message, is_class_e, is_declared_message_id, is_detected_user_id
from .group import delete_message, get_message, leave_group
from .ids import init_group_id, init_user_id
from .telegram import send_message, send_photo, send_report_message
from .timers import update_admins
from .user import add_bad_user, ban_user, terminate_user

# Enable logging
logger = logging.getLogger(__name__)


def receive_add_except(client: Client, data: dict) -> bool:
    # Receive a object and add it to except list
    try:
        the_id = data["id"]
        the_type = data["type"]
        # Receive except channels
        if the_type == "channel":
            glovar.except_ids["channels"].add(the_id)
        # Receive except contents
        elif the_type in {"long", "temp"}:
            message = get_message(client, glovar.logging_channel_id, the_id)
            if not message:
                return True

            record = get_report_record(message)
            if "名称" in record["rule"]:
                if record["name"]:
                    glovar.except_ids["long"].add(record["name"])
                    glovar.bad_ids["temp"].discard(record["name"])

                if record["from"]:
                    glovar.except_ids["long"].add(record["from"])
                    glovar.bad_ids["temp"].discard(record["from"])

                save("bad_ids")

            if "简介" in record["rule"]:
                if record["bio"]:
                    glovar.except_ids["long"].add(record["bio"])
                    glovar.bad_ids["temp"].discard(record["bio"])

                save("bad_ids")

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            content = get_content(message)
            if content:
                glovar.except_ids[the_type].add(content)

        save("except_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive add except error: {e}", exc_info=True)

    return False


def receive_add_bad(client: Client, sender: str, data: dict) -> bool:
    # Receive bad users ,channels, and contents that other bots shared
    try:
        the_id = data["id"]
        the_type = data["type"]
        if the_type == "user":
            glovar.bad_ids["users"].add(the_id)
        elif sender == "MANAGE" and the_type == "channel":
            glovar.bad_ids["channels"].add(the_id)
        elif sender == "MANAGE" and the_type == "temp":
            message = get_message(client, glovar.logging_channel_id, the_id)
            if not message:
                return True

            record = get_report_record(message)
            if "WARN" not in {record["origin"], record["project"]}:
                return True

            if record["type"] == "服务消息":
                if record["name"]:
                    glovar.bad_ids["temp"].add(record["name"])
                    glovar.except_ids["long"].discard(record["name"])

                save("except_ids")

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            content = get_content(message)
            if content:
                glovar.bad_ids[the_type].add(content)

        save("bad_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive add bad error: {e}", exc_info=True)

    return False


def receive_avatar(client: Client, message: Message, data: dict) -> bool:
    # Receive avatar
    image_path = ""
    if glovar.locks["message"].acquire():
        try:
            gid = data["group_id"]
            uid = data["user_id"]
            mid = data["message_id"]
            if glovar.admin_ids.get(gid):
                # Do not check admin's avatar
                if uid in glovar.admin_ids[gid]:
                    return True

                # Do not check Class D personnel's avatar
                if uid in glovar.bad_ids["users"]:
                    return True

                image = receive_file_data(client, message, True)
                if not image:
                    return True

                image_path = get_new_path()
                image.save(image_path, "PNG")
                if is_avatar_image(image_path):
                    result = send_photo(client, glovar.logging_channel_id, image_path)
                    if not result:
                        return True

                    text = (f"项目编号：{code(glovar.sender)}\n"
                            f"用户 ID：{code(uid)}\n"
                            f"操作等级：{code('自动封禁')}\n"
                            f"规则：{code('头像分析')}\n")
                    result = result.message_id
                    result = send_message(client, glovar.logging_channel_id, text, result)
                    if not result:
                        return True

                    add_bad_user(client, uid)
                    ban_user(client, gid, uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    ask_for_help(client, "ban", gid, uid)
                    send_debug(client, message.chat, "头像封禁", uid, mid, result)

            return True
        except Exception as e:
            logger.warning(f"Receive avatar error: {e}", exc_info=True)
        finally:
            delete_file(image_path)
            glovar.locks["message"].release()

    return False


def receive_config_commit(data: dict) -> bool:
    # Receive config commit
    try:
        gid = data["group_id"]
        config = data["config"]
        glovar.configs[gid] = config
        save("configs")

        return True
    except Exception as e:
        logger.warning(f"Receive config commit error: {e}", exc_info=True)

    return False


def receive_config_reply(client: Client, data: dict) -> bool:
    # Receive config reply
    try:
        gid = data["group_id"]
        uid = data["user_id"]
        link = data["config_link"]
        text = (f"管理员：{code(uid)}\n"
                f"操作：{code('更改设置')}\n"
                f"说明：{code('请点击下方按钮进行设置')}\n")
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="前往设置",
                        url=link
                    )
                ]
            ]
        )
        thread(send_report_message, (180, client, gid, text, None, markup))

        return True
    except Exception as e:
        logger.warning(f"Receive config reply error: {e}", exc_info=True)

    return False


def receive_declared_message(data: dict) -> bool:
    # Update declared message's id
    try:
        gid = data["group_id"]
        mid = data["message_id"]
        if glovar.admin_ids.get(gid):
            if init_group_id(gid):
                glovar.declared_message_ids[gid].add(mid)
                return True
    except Exception as e:
        logger.warning(f"Receive declared message error: {e}", exc_info=True)

    return False


def receive_file_data(client: Client, message: Message, decrypt: bool = False) -> Any:
    # Receive file's data from exchange channel
    data = None
    try:
        if message.document:
            file_id = message.document.file_id
            path = get_downloaded_path(client, file_id)
            if path:
                if decrypt:
                    # Decrypt the file, save to the tmp directory
                    path_decrypted = get_new_path()
                    crypt_file("decrypt", path, path_decrypted)
                    path_final = path_decrypted
                else:
                    # Read the file directly
                    path_decrypted = ""
                    path_final = path

                with open(path_final, "rb") as f:
                    data = pickle.load(f)

                for f in {path, path_decrypted}:
                    thread(delete_file, (f,))
    except Exception as e:
        logger.warning(f"Receive file error: {e}", exc_info=True)

    return data


def receive_preview(client: Client, message: Message, data: dict) -> bool:
    # Receive message's preview
    if glovar.locks["message"].acquire():
        try:
            gid = data["group_id"]
            uid = data["user_id"]
            mid = data["message_id"]
            if glovar.admin_ids.get(gid):
                # Do not check admin's message
                if uid in glovar.admin_ids[gid]:
                    return True

                preview = receive_file_data(client, message, True)
                if preview:
                    text = preview["text"]
                    image = preview["image"]
                    if image:
                        image_path = get_new_path()
                        image.save(image_path, "PNG")
                    else:
                        image_path = None

                    if (not is_declared_message_id(gid, mid)
                            and not is_detected_user_id(gid, uid)):
                        the_message = get_message(client, gid, mid)
                        if not the_message:
                            return True

                        detection = is_bad_message(client, the_message, text, image_path)
                        if detection:
                            if not is_class_e(None, the_message):
                                url = get_stripped_link(preview["url"])
                                glovar.contents[url] = detection
                                terminate_user(client, the_message, "url")

            return True
        except Exception as e:
            logger.warning(f"Receive preview error: {e}", exc_info=True)
        finally:
            glovar.locks["message"].release()

    return False


def receive_leave_approve(client: Client, data: dict) -> bool:
    # Receive leave approve
    try:
        admin_id = data["admin_id"]
        the_id = data["group_id"]
        reason = data["reason"]
        if reason == "permissions":
            reason = "权限缺失"
        elif reason == "user":
            reason = "缺失 USER"

        if glovar.admin_ids.get(the_id, {}):
            text = get_debug_text(client, the_id)
            text += (f"项目管理员：{user_mention(admin_id)}\n"
                     f"状态：{code('已批准退出该群组')}\n")
            if reason:
                text += f"原因：{code(reason)}\n"

            leave_group(client, the_id)
            thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Receive leave approve error: {e}", exc_info=True)

    return False


def receive_report_ids(client: Client, message: Message) -> bool:
    # Receive report ids
    try:
        report_ids = receive_file_data(client, message, True)
        if report_ids:
            glovar.report_ids = report_ids
            save("report_ids")
    except Exception as e:
        logger.warning(f"Receive report ids error: {e}", exc_info=True)

    return False


def receive_refresh(client: Client, data: int) -> bool:
    # Receive refresh
    try:
        aid = data
        update_admins(client)
        text = (f"项目编号：{general_link(glovar.project_name, glovar.project_link)}\n"
                f"项目管理员：{user_mention(aid)}\n"
                f"执行操作：{code('刷新群管列表')}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Receive refresh error: {e}", exc_info=True)

    return False


def receive_regex(client: Client, message: Message, data: str) -> bool:
    # Receive regex
    if glovar.locks["regex"].acquire():
        try:
            file_name = data
            word_type = file_name.split("_")[0]
            if word_type not in glovar.regex:
                return True

            words_data = receive_file_data(client, message, True)
            if words_data:
                pop_set = set(eval(f"glovar.{file_name}")) - set(words_data)
                new_set = set(words_data) - set(eval(f"glovar.{file_name}"))
                for word in pop_set:
                    eval(f"glovar.{file_name}").pop(word, 0)

                for word in new_set:
                    eval(f"glovar.{file_name}")[word] = 0

                save(file_name)

            return True
        except Exception as e:
            logger.warning(f"Receive regex error: {e}", exc_info=True)
        finally:
            glovar.locks["regex"].release()

    return False


def receive_remove_bad(client: Client, sender: str, data: dict) -> bool:
    # Receive removed bad objects
    try:
        the_id = data["id"]
        the_type = data["type"]
        if sender == "MANAGE" and the_type == "channel":
            glovar.bad_ids["channels"].discard(the_id)
        elif the_type == "user":
            glovar.bad_ids["users"].discard(the_id)
            glovar.watch_ids["ban"].pop(the_id, {})
            glovar.watch_ids["delete"].pop(the_id, {})
            if glovar.user_ids.get(the_id):
                glovar.user_ids[the_id] = deepcopy(glovar.default_user_status)

            save("watch_ids")
            save("user_ids")
        elif sender == "MANAGE" and the_type == "temp":
            message = get_message(client, glovar.logging_channel_id, the_id)
            if not message:
                return True

            record = get_report_record(message)
            if "WARN" not in {record["origin"], record["project"]}:
                return True

            if record["type"] == "服务消息":
                if record["name"]:
                    glovar.bad_ids["temp"].discard(record["name"])

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            content = get_content(message)
            if content:
                glovar.bad_ids[the_type].discard(content)

        save("bad_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove bad error: {e}", exc_info=True)

    return False


def receive_remove_except(client: Client, data: dict) -> bool:
    # Receive a object and remove it from except list
    try:
        the_id = data["id"]
        the_type = data["type"]
        # Receive except channels
        if the_type == "channel":
            glovar.except_ids["channels"].discard(the_id)
            save("except_ids")
        # Receive except contents
        elif the_type in {"long", "temp"}:
            message = get_message(client, glovar.logging_channel_id, the_id)
            if not message:
                return True

            record = get_report_record(message)
            if "名称" in record["rule"]:
                if record["name"]:
                    glovar.except_ids["long"].discard(record["name"])

                if record["from"]:
                    glovar.except_ids["long"].discard(record["from"])

            if "简介" in record["rule"]:
                if record["bio"]:
                    glovar.except_ids["long"].discard(record["bio"])

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            content = get_content(message)
            if content:
                glovar.except_ids[the_type].discard(content)

        save("except_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove except error: {e}", exc_info=True)

    return False


def receive_remove_watch(data: dict) -> bool:
    # Receive removed watching users
    try:
        uid = data["id"]
        the_type = data["type"]
        if the_type == "all":
            glovar.watch_ids["ban"].pop(uid, 0)
            glovar.watch_ids["delete"].pop(uid, 0)

        save("watch_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove watch error: {e}", exc_info=True)

    return False


def receive_status_ask(client: Client, data: dict) -> bool:
    # Receive version info request
    try:
        aid = data["admin_id"]
        mid = data["message_id"]
        now = get_now()
        new_count = 0
        bad_count = len(glovar.bad_ids["users"])
        user_ids = deepcopy(glovar.user_ids)
        for uid in user_ids:
            if any([now - user_ids[uid]["join"][gid] < glovar.time_new for gid in user_ids[uid]["join"]]):
                new_count += 1

        status = {
            "昵称复查": f"{new_count} 名",
            "黑名单": f"{bad_count} 名"
        }
        file = data_to_file(status)
        share_data(
            client=client,
            receivers=["MANAGE"],
            action="status",
            action_type="reply",
            data={
                "admin_id": aid,
                "message_id": mid
            },
            file=file
        )

        return True
    except Exception as e:
        logger.warning(f"Receive version ask error: {e}", exc_info=True)

    return False


def receive_text_data(message: Message) -> dict:
    # Receive text's data from exchange channel
    data = {}
    try:
        text = get_text(message)
        if text:
            data = loads(text)
    except Exception as e:
        logger.warning(f"Receive data error: {e}")

    return data


def receive_user_score(client: Client, project: str, data: dict) -> bool:
    # Receive and update user's score
    try:
        project = project.lower()
        uid = data["id"]
        init_user_id(uid)
        score = data["score"]
        glovar.user_ids[uid][project] = score
        save("user_ids")
        total_score = sum(glovar.user_ids[uid]["score"].values())
        if total_score >= 3.0:
            ask_for_help(client, "delete", 0, uid, "global")

        return True
    except Exception as e:
        logger.warning(f"Receive user score error: {e}", exc_info=True)

    return False


def receive_watch_user(data: dict) -> bool:
    # Receive watch users that other bots shared
    try:
        the_type = data["type"]
        uid = data["id"]
        until = data["until"]

        # Decrypt the data
        until = crypt_str("decrypt", until, glovar.key)
        until = get_int(until)

        # Add to list
        if the_type == "ban":
            glovar.watch_ids["ban"][uid] = until
        elif the_type == "delete":
            glovar.watch_ids["delete"][uid] = until
        else:
            return False

        save("watch_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive watch user error: {e}", exc_info=True)

    return False
