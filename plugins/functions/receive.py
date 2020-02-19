# SCP-079-NOSPAM - Block spam in groups
# Copyright (C) 2019-2020 SCP-079 <https://scp-079.org>
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
from os import rename
from typing import Any

from pyrogram import Client, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import glovar
from .channel import ask_for_help, declare_message, get_content, get_debug_text, send_debug, share_data
from .etc import code, crypt_str, delay, general_link, get_int, get_now, get_report_record, get_stripped_link, get_text
from .etc import lang, mention_id, message_link, thread
from .file import crypt_file, data_to_file, delete_file, get_new_path, get_downloaded_path, save
from .filters import is_avatar_image, is_bad_message, is_ban_text, is_class_e
from .filters import is_declared_message_id, is_detected_user_id, is_wb_text
from .group import delete_message, get_config_text, get_message, leave_group
from .ids import init_group_id, init_user_id
from .image import get_image_hash
from .telegram import send_message, send_photo, send_report_message
from .timers import update_admins
from .user import add_bad_user, ban_user, global_delete_score, global_delete_watch
from .user import remove_contacts_info, terminate_user

# Enable logging
logger = logging.getLogger(__name__)


def receive_add_bad(client: Client, sender: str, data: dict) -> bool:
    # Receive bad users ,channels, and contents that other bots shared
    try:
        # Basic data
        the_id = data["id"]
        the_type = data["type"]

        # Receive bad channel
        if sender == "MANAGE" and the_type == "channel":
            glovar.bad_ids["channels"].add(the_id)

        # Receive bad user
        if the_type == "user":
            glovar.bad_ids["users"].add(the_id)

        # Receive bad content
        if sender == "MANAGE" and the_type == "content":
            message = get_message(client, glovar.logging_channel_id, the_id)

            if not message:
                return True

            record = get_report_record(message)

            if "WARN" not in {record["origin"], record["project"]}:
                return True

            if record["type"] == lang("ser"):
                if record["name"]:
                    glovar.bad_ids["contents"].add(record["name"])
                    glovar.except_ids["long"].discard(record["name"])
                    glovar.except_ids["temp"].discard(record["name"])
                    save("except_ids")

                if record["bio"] and is_wb_text(record["bio"], False):
                    glovar.bad_ids["contents"].add(record["bio"])
                    glovar.except_ids["long"].discard(record["bio"])
                    glovar.except_ids["temp"].discard(record["bio"])
                    save("except_ids")

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            message_text = get_text(message, True, True)

            if message_text and is_ban_text(message_text, False):
                return True

            content = get_content(message)

            if content:
                glovar.bad_ids["contents"].add(content)
                glovar.except_ids["long"].discard(content)
                glovar.except_ids["temp"].discard(content)
                save("except_ids")

            image_hash = get_image_hash(client, message)

            if image_hash:
                glovar.bad_ids["contents"].add(image_hash)

        save("bad_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive add bad error: {e}", exc_info=True)

    return False


def receive_add_except(client: Client, data: dict) -> bool:
    # Receive a object and add it to except list
    try:
        # Basic data
        the_id = data["id"]
        the_type = data["type"]

        # Receive except channel
        if the_type == "channel":
            glovar.except_ids["channels"].add(the_id)

        # Receive except content
        if the_type in {"long", "temp"}:
            message = get_message(client, glovar.logging_channel_id, the_id)

            if not message:
                return True

            record = get_report_record(message)

            if lang("name") in record["rule"]:
                if record["name"]:
                    glovar.except_ids["long"].add(record["name"])
                    glovar.bad_ids["contents"].discard(record["name"])

                if record["from"]:
                    glovar.except_ids["long"].add(record["from"])
                    glovar.bad_ids["contents"].discard(record["from"])

                save("bad_ids")

            if lang("bio") in record["rule"]:
                if record["bio"]:
                    glovar.except_ids["long"].add(record["bio"])
                    glovar.bad_ids["contents"].discard(record["bio"])

                save("bad_ids")

            if record["game"]:
                glovar.except_ids["long"].add(record["game"])

            if record["rule"] in {lang("avatar_examine"), lang("avatar_recheck")}:
                uid = record["uid"]
                share_data(
                    client=client,
                    receivers=["AVATAR"],
                    action="add",
                    action_type="except",
                    data={
                        "the_id": uid,
                        "the_type": "long"
                    }
                )
                return True

            thread(remove_contacts_info, (message, ""))

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            if (message.sticker or message.via_bot) and record["more"]:
                glovar.except_ids["long"].add(record["more"])

            content = get_content(message)

            if content:
                glovar.except_ids[the_type].add(content)
                glovar.bad_ids["contents"].discard(content)
                save("bad_ids")
                glovar.contents.pop(content, "")

            image_hash = get_image_hash(client, message)

            if image_hash:
                glovar.except_ids["temp"].add(image_hash)

        save("except_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive add except error: {e}", exc_info=True)

    return False


def receive_avatar(client: Client, message: Message, data: dict) -> bool:
    # Receive avatar
    image_path = ""
    glovar.locks["message"].acquire()
    try:
        # Basic data
        gid = data["group_id"]
        uid = data["user_id"]
        mid = data["message_id"]

        if not glovar.admin_ids.get(gid):
            return True

        # Do not check admin's avatar
        if uid in glovar.admin_ids[gid]:
            return True

        # Do not check Class D personnel's avatar
        if uid in glovar.bad_ids["users"]:
            return True

        image = receive_file_data(client, message)

        if not image:
            return True

        image_path = get_new_path()
        image.save(image_path, "PNG")

        if not is_avatar_image(image_path):
            return True

        rename(image_path, f"{image_path}.png")
        image_path = f"{image_path}.png"
        result = send_photo(client, glovar.logging_channel_id, image_path)

        if not result:
            return True

        if mid:
            text = (f"{lang('project')}{lang('colon')}{code(glovar.sender)}\n"
                    f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                    f"{lang('level')}{lang('colon')}{code(lang('auto_ban'))}\n"
                    f"{lang('rule')}{lang('colon')}{code(lang('avatar_examine'))}\n")
            result = result.message_id
            result = send_message(client, glovar.logging_channel_id, text, result)

            if not result:
                return True

            declare_message(client, gid, mid)
            ban_user(client, gid, uid)
            delete_message(client, gid, mid)
            ask_for_help(client, "ban", gid, uid)
            add_bad_user(client, uid)
            send_debug(
                client=client,
                chat=gid,
                action=lang("avatar_ban"),
                uid=uid,
                mid=mid,
                em=result
            )
        else:
            text = (f"{lang('project')}{lang('colon')}{code(glovar.sender)}\n"
                    f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                    f"{lang('level')}{lang('colon')}{code(lang('auto_ban'))}\n"
                    f"{lang('rule')}{lang('colon')}{code(lang('avatar_recheck'))}\n")
            result = result.message_id
            result = send_message(client, glovar.logging_channel_id, text, result)

            if not result:
                return True

            ban_user(client, gid, uid)
            ask_for_help(client, "ban", gid, uid)
            add_bad_user(client, uid)
            text = get_debug_text(client, gid)
            text += (f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                     f"{lang('action')}{lang('colon')}{code(lang('avatar_ban'))}\n"
                     f"{lang('evidence')}{lang('colon')}{general_link(result.message_id, message_link(result))}\n")
            thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Receive avatar error: {e}", exc_info=True)
    finally:
        thread(delete_file, (image_path,))
        glovar.locks["message"].release()

    return False


def receive_captcha_kicked_user(data: dict) -> bool:
    # Receive CAPTCHA kicked user
    glovar.locks["message"].acquire()
    try:
        # Basic data
        gid = data["group_id"]
        uid = data["user_id"]

        # Check user status
        if not glovar.user_ids.get(uid, {}):
            return True

        glovar.user_ids[uid]["join"].pop(gid, 0)
        save("user_ids")
    except Exception as e:
        logger.warning(f"Receive captcha kicked user error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_clear_data(client: Client, data_type: str, data: dict) -> bool:
    # Receive clear data command
    glovar.locks["message"].acquire()
    try:
        # Basic data
        aid = data["admin_id"]
        the_type = data["type"]

        # Clear bad data
        if data_type == "bad":
            if the_type == "channels":
                glovar.bad_ids["channels"] = set()
            elif the_type == "contacts":
                glovar.bad_ids["contacts"] = set()
            elif the_type == "contents":
                glovar.bad_ids["contents"] = set()
            elif the_type == "users":
                glovar.bad_ids["users"] = set()

            save("bad_ids")

        # Clear except data
        if data_type == "except":
            if the_type == "channels":
                glovar.except_ids["channels"] = set()
            elif the_type == "long":
                glovar.except_ids["long"] = set()
            elif the_type == "temp":
                glovar.except_ids["temp"] = set()

            save("except_ids")

        # Clear user data
        if data_type == "user":
            if the_type == "all":
                glovar.user_ids = {}
            elif the_type == "new":
                for uid in list(glovar.user_ids):
                    glovar.user_ids[uid]["join"] = {}

            save("user_ids")

        # Clear watch data
        if data_type == "watch":
            if the_type == "all":
                glovar.watch_ids = {
                    "ban": {},
                    "delete": {}
                }
            elif the_type == "ban":
                glovar.watch_ids["ban"] = {}
            elif the_type == "delete":
                glovar.watch_ids["delete"] = {}

            save("watch_ids")

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('admin_project')}{lang('colon')}{mention_id(aid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('clear'))}\n"
                f"{lang('more')}{lang('colon')}{code(f'{data_type} {the_type}')}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))
    except Exception as e:
        logger.warning(f"Receive clear data: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_config_commit(data: dict) -> bool:
    # Receive config commit
    try:
        # Basic data
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
        # Basic data
        gid = data["group_id"]
        uid = data["user_id"]
        link = data["config_link"]

        text = (f"{lang('admin')}{lang('colon')}{code(uid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('config_change'))}\n"
                f"{lang('description')}{lang('colon')}{code(lang('config_button'))}\n")
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=lang("config_go"),
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


def receive_config_show(client: Client, data: dict) -> bool:
    # Receive config show request
    try:
        # Basic Data
        aid = data["admin_id"]
        mid = data["message_id"]
        gid = data["group_id"]

        # Generate report message's text
        result = (f"{lang('admin')}{lang('colon')}{mention_id(aid)}\n"
                  f"{lang('action')}{lang('colon')}{code(lang('config_show'))}\n"
                  f"{lang('group_id')}{lang('colon')}{code(gid)}\n")

        if glovar.configs.get(gid, {}):
            result += get_config_text(glovar.configs[gid])
        else:
            result += (f"{lang('status')}{lang('colon')}{code(lang('status_failed'))}\n"
                       f"{lang('reason')}{lang('colon')}{code(lang('reason_none'))}\n")

        # Send the text data
        file = data_to_file(result)
        share_data(
            client=client,
            receivers=["MANAGE"],
            action="config",
            action_type="show",
            data={
                "admin_id": aid,
                "message_id": mid,
                "group_id": gid
            },
            file=file
        )

        return True
    except Exception as e:
        logger.warning(f"Receive config show error: {e}", exc_info=True)

    return False


def receive_declared_message(data: dict) -> bool:
    # Update declared message's id
    try:
        # Basic data
        gid = data["group_id"]
        mid = data["message_id"]

        if not glovar.admin_ids.get(gid):
            return True

        if init_group_id(gid):
            glovar.declared_message_ids[gid].add(mid)

        return True
    except Exception as e:
        logger.warning(f"Receive declared message error: {e}", exc_info=True)

    return False


def receive_file_data(client: Client, message: Message, decrypt: bool = True) -> Any:
    # Receive file's data from exchange channel
    data = None
    try:
        if not message.document:
            return None

        file_id = message.document.file_id
        file_ref = message.document.file_ref
        path = get_downloaded_path(client, file_id, file_ref)

        if not path:
            return None

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


def receive_leave_approve(client: Client, data: dict) -> bool:
    # Receive leave approve
    try:
        # Basic data
        admin_id = data["admin_id"]
        the_id = data["group_id"]
        reason = data["reason"]

        if reason in {"permissions", "user"}:
            reason = lang(f"reason_{reason}")

        if not glovar.admin_ids.get(the_id):
            return True

        text = get_debug_text(client, the_id)
        text += (f"{lang('admin_project')}{lang('colon')}{mention_id(admin_id)}\n"
                 f"{lang('status')}{lang('colon')}{code(lang('leave_approve'))}\n")

        if reason:
            text += f"{lang('reason')}{lang('colon')}{code(reason)}\n"

        leave_group(client, the_id)
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Receive leave approve error: {e}", exc_info=True)

    return False


def receive_preview(client: Client, message: Message, data: dict) -> bool:
    # Receive message's preview
    glovar.locks["message"].acquire()
    try:
        # Basic data
        gid = data["group_id"]
        uid = data["user_id"]
        mid = data["message_id"]
        now = message.date or get_now()

        # Check if the bot joined the group
        if not glovar.admin_ids.get(gid):
            return True

        # Do not check admin's message
        if uid in glovar.admin_ids[gid]:
            return True

        # Get the preview
        preview = receive_file_data(client, message)

        if not preview:
            return True

        # Read the data
        url = get_stripped_link(preview["url"])
        text = preview["text"]
        image = preview["image"]

        if image:
            image_path = get_new_path()
            image.save(image_path, "PNG")
        else:
            image_path = None

        # Check status
        if is_declared_message_id(gid, mid) or is_detected_user_id(gid, uid, now):
            return True

        # Get the message
        the_message = get_message(client, gid, mid)

        if not the_message or is_class_e(None, the_message):
            return True

        # Detect
        detection = is_bad_message(client, the_message, text, image_path)

        if detection:
            result = terminate_user(client, the_message, the_message.from_user, detection)

            if result and url and detection != "true":
                glovar.contents[url] = detection

        return True
    except Exception as e:
        logger.warning(f"Receive preview error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_refresh(client: Client, data: int) -> bool:
    # Receive refresh
    try:
        # Basic data
        aid = data

        # Update admins
        update_admins(client)

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('admin_project')}{lang('colon')}{mention_id(aid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('refresh'))}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Receive refresh error: {e}", exc_info=True)

    return False


def receive_regex(client: Client, message: Message, data: str) -> bool:
    # Receive regex
    glovar.locks["regex"].acquire()
    try:
        file_name = data
        word_type = file_name.split("_")[0]

        if word_type not in glovar.regex:
            return True

        words_data = receive_file_data(client, message)

        if not words_data:
            return True

        pop_set = set(eval(f"glovar.{file_name}")) - set(words_data)
        new_set = set(words_data) - set(eval(f"glovar.{file_name}"))

        for word in pop_set:
            eval(f"glovar.{file_name}").pop(word, 0)

        for word in new_set:
            eval(f"glovar.{file_name}")[word] = 0

        save(file_name)

        # Regenerate special characters dictionary if possible
        if file_name in {"spc_words", "spe_words"}:
            special = file_name.split("_")[0]
            exec(f"glovar.{special}_dict = {{}}")

            for rule in words_data:
                # Check keys
                if "[" not in rule:
                    continue

                # Check value
                if "?#" not in rule:
                    continue

                keys = rule.split("]")[0][1:]
                value = rule.split("?#")[1][1]

                for k in keys:
                    eval(f"glovar.{special}_dict")[k] = value

        return True
    except Exception as e:
        logger.warning(f"Receive regex error: {e}", exc_info=True)
    finally:
        glovar.locks["regex"].release()

    return False


def receive_remove_bad(client: Client, data: dict) -> bool:
    # Receive removed bad objects
    try:
        # Basic data
        the_id = data["id"]
        the_type = data["type"]

        # Remove bad channel
        if the_type == "channel":
            glovar.bad_ids["channels"].discard(the_id)

        # Remove bad user
        if the_type == "user":
            glovar.bad_ids["users"].discard(the_id)
            glovar.watch_ids["ban"].pop(the_id, {})
            glovar.watch_ids["delete"].pop(the_id, {})
            save("watch_ids")
            glovar.user_ids[the_id] = deepcopy(glovar.default_user_status)
            save("user_ids")

        # Remove bad contact
        if the_type == "contact":
            thread(remove_contacts_info, (None, the_id))

        # Remove bad content
        if the_type == "content":
            message = get_message(client, glovar.logging_channel_id, the_id)

            if not message:
                return True

            record = get_report_record(message)

            if "WARN" not in {record["origin"], record["project"]}:
                return True

            if record["type"] == lang("ser"):
                if record["name"]:
                    glovar.bad_ids["contents"].discard(record["name"])

                if record["bio"]:
                    glovar.bad_ids["contents"].discard(record["bio"])

                save("bad_ids")

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            content = get_content(message)

            if content:
                glovar.bad_ids["contents"].discard(content)

            image_hash = get_image_hash(client, message)

            if image_hash:
                glovar.bad_ids["contents"].discard(image_hash)

        save("bad_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove bad error: {e}", exc_info=True)

    return False


def receive_remove_except(client: Client, data: dict) -> bool:
    # Receive a object and remove it from except list
    try:
        # Basic data
        the_id = data["id"]
        the_type = data["type"]

        # Receive except channel
        if the_type == "channel":
            glovar.except_ids["channels"].discard(the_id)

        # Receive except content
        if the_type in {"long", "temp"}:
            message = get_message(client, glovar.logging_channel_id, the_id)

            if not message:
                return True

            record = get_report_record(message)

            if lang("name") in record["rule"]:
                if record["name"]:
                    glovar.except_ids["long"].discard(record["name"])

                if record["from"]:
                    glovar.except_ids["long"].discard(record["from"])

            if lang("bio") in record["rule"]:
                if record["bio"]:
                    glovar.except_ids["long"].discard(record["bio"])

            if record["game"]:
                glovar.except_ids["long"].discard(record["game"])

            if record["rule"] in {lang("avatar_examine"), lang("avatar_recheck")}:
                uid = record["uid"]
                share_data(
                    client=client,
                    receivers=["AVATAR"],
                    action="remove",
                    action_type="except",
                    data={
                        "the_id": uid,
                        "the_type": "long"
                    }
                )
                return True

            if message.reply_to_message:
                message = message.reply_to_message
            else:
                return True

            if (message.sticker or message.via_bot) and record["more"]:
                glovar.except_ids["long"].discard(record["more"])

            if message.sticker and record["more"]:
                glovar.except_ids["long"].discard(message.sticker.set_name)
                glovar.except_ids["long"].discard(record["more"])

            content = get_content(message)

            if content:
                glovar.except_ids[the_type].discard(content)

        save("except_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove except error: {e}", exc_info=True)

    return False


def receive_remove_score(data: int) -> bool:
    # Receive remove user's score
    glovar.locks["message"].acquire()
    try:
        # Basic data
        uid = data

        if not glovar.user_ids.get(uid):
            return True

        glovar.user_ids[uid] = deepcopy(glovar.default_user_status)
        save("user_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove score error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_remove_watch(data: dict) -> bool:
    # Receive removed watching users
    try:
        # Basic data
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


def receive_report_ids(client: Client, message: Message, data: str) -> bool:
    # Receive report ids
    try:
        if data == "report":
            report_ids = receive_file_data(client, message)

            if report_ids:
                glovar.report_ids = report_ids
                save("report_ids")
    except Exception as e:
        logger.warning(f"Receive report ids error: {e}", exc_info=True)

    return False


def receive_rollback(client: Client, message: Message, data: dict) -> bool:
    # Receive rollback data
    try:
        # Basic data
        aid = data["admin_id"]
        the_type = data["type"]
        the_data = receive_file_data(client, message)

        if not the_data:
            return True

        exec(f"glovar.{the_type} = the_data")
        save(the_type)

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('admin_project')}{lang('colon')}{mention_id(aid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('rollback'))}\n"
                f"{lang('more')}{lang('colon')}{code(the_type)}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))
    except Exception as e:
        logger.warning(f"Receive rollback error: {e}", exc_info=True)

    return False


def receive_status_ask(client: Client, data: dict) -> bool:
    # Receive version info request
    glovar.locks["message"].acquire()
    try:
        # Basic data
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
            lang("name_recheck"): f"{new_count} {lang('members')}",
            lang("blacklist"): f"{bad_count} {lang('members')}"
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
    finally:
        glovar.locks["message"].release()

    return False


def receive_text_data(message: Message) -> dict:
    # Receive text's data from exchange channel
    data = {}
    try:
        text = get_text(message)

        if not text:
            return {}

        data = loads(text)
    except Exception as e:
        logger.warning(f"Receive text data error: {e}")

    return data


def receive_user_score(client: Client, project: str, data: dict) -> bool:
    # Receive and update user's score
    glovar.locks["message"].acquire()
    try:
        # Basic data
        project = project.lower()
        uid = data["id"]

        if not init_user_id(uid):
            return True

        score = data["score"]
        glovar.user_ids[uid]["score"][project] = score
        save("user_ids")

        # Global delete
        delay(10, global_delete_score, [client, uid])

        return True
    except Exception as e:
        logger.warning(f"Receive user score error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_watch_user(client: Client, data: dict, from_watch: bool = False) -> bool:
    # Receive watch users that other bots shared
    try:
        # Basic data
        the_type = data["type"]
        uid = data["id"]
        until = data["until"]

        # Decrypt the data
        until = crypt_str("decrypt", until, glovar.key)
        until = get_int(until)

        # Add to list
        if the_type == "ban":
            glovar.watch_ids["ban"][uid] = until

            # Global delete
            if not from_watch:
                save("watch_ids")
                return True

            mid = data["message_id"]
            delay(10, global_delete_watch, [client, uid, mid])

        elif the_type == "delete":
            glovar.watch_ids["delete"][uid] = until
        else:
            return False

        save("watch_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive watch user error: {e}", exc_info=True)

    return False
