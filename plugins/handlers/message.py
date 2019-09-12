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

from pyrogram import Client, Filters, Message

from .. import glovar
from ..functions.channel import get_content, get_debug_text
from ..functions.etc import code, get_full_name, get_now, thread, user_mention
from ..functions.file import save
from ..functions.filters import class_c, class_d, declared_message, exchange_channel, from_user, hide_channel
from ..functions.filters import is_bad_message, is_bio_text, is_declared_message, is_new_user, is_nm_text
from ..functions.filters import new_group, test_group
from ..functions.group import leave_group
from ..functions.ids import init_group_id, init_user_id
from ..functions.receive import receive_add_bad, receive_add_except, receive_avatar, receive_config_commit
from ..functions.receive import receive_config_reply, receive_declared_message, receive_preview, receive_leave_approve
from ..functions.receive import receive_regex, receive_refresh, receive_remove_bad, receive_remove_except
from ..functions.receive import receive_remove_score, receive_remove_watch, receive_report_ids
from ..functions.receive import receive_status_ask, receive_text_data, receive_user_score, receive_watch_user
from ..functions.telegram import get_admins, get_user_bio, send_message
from ..functions.tests import nospam_test
from ..functions.timers import send_count
from ..functions.user import terminate_user

# Enable logging
logger = logging.getLogger(__name__)


@Client.on_message(Filters.incoming & Filters.group & ~test_group & from_user & ~Filters.service
                   & ~class_c & ~class_d & ~declared_message)
def check(client: Client, message: Message) -> bool:
    # Check the messages sent from groups
    if glovar.locks["message"].acquire():
        try:
            # Check declare status
            if is_declared_message(None, message):
                return True

            # Check bad message
            content = get_content(message)
            detection = is_bad_message(client, message)
            if detection:
                glovar.contents[content] = detection
                return terminate_user(client, message, message.from_user, detection)
            elif message.sticker:
                glovar.except_ids["temp"].add(content)
                save("except_ids")

            return True
        except Exception as e:
            logger.warning(f"Check error: {e}", exc_info=True)
        finally:
            glovar.locks["message"].release()

    return False


@Client.on_message(Filters.incoming & Filters.group & ~test_group & from_user & Filters.new_chat_members & ~new_group
                   & ~class_c & ~declared_message)
def check_join(client: Client, message: Message) -> bool:
    # Check new joined user
    if glovar.locks["message"].acquire():
        try:
            gid = message.chat.id
            for new in message.new_chat_members:
                uid = new.id
                # Check record
                if uid in glovar.bad_ids["users"]:
                    continue

                if not is_new_user(new):
                    # Check name
                    name = get_full_name(new)
                    if name and is_nm_text(name):
                        terminate_user(client, message, new, "ban name")
                    elif name in glovar.bad_ids["contents"]:
                        terminate_user(client, message, new, "ban name record")

                    # Check bio
                    bio = get_user_bio(client, new.username or new.id)
                    if bio and is_bio_text(bio):
                        terminate_user(client, message, new, f"ban bio {bio}")

                # Check bot
                if glovar.configs[gid]["bot"] and new.is_bot:
                    terminate_user(client, message, new, "ban bot")

                # Update user's join status
                if init_user_id(uid):
                    glovar.user_ids[uid]["join"][gid] = get_now()
                    save("user_ids")

            return True
        except Exception as e:
            logger.warning(f"Check join error: {e}", exc_info=True)
        finally:
            glovar.locks["message"].release()

    return False


@Client.on_message(Filters.incoming & Filters.channel & hide_channel
                   & ~Filters.command(glovar.all_commands, glovar.prefix), group=-1)
def exchange_emergency(_: Client, message: Message) -> bool:
    # Sent emergency channel transfer request
    try:
        # Read basic information
        data = receive_text_data(message)
        if data:
            sender = data["from"]
            receivers = data["to"]
            action = data["action"]
            action_type = data["type"]
            data = data["data"]
            if "EMERGENCY" in receivers:
                if action == "backup":
                    if action_type == "hide":
                        if data is True:
                            glovar.should_hide = data
                        elif data is False and sender == "MANAGE":
                            glovar.should_hide = data

        return True
    except Exception as e:
        logger.warning(f"Exchange emergency error: {e}", exc_info=True)

    return False


@Client.on_message(Filters.incoming & Filters.group & ~test_group & from_user
                   & (Filters.new_chat_members | Filters.group_chat_created | Filters.supergroup_chat_created)
                   & new_group)
def init_group(client: Client, message: Message) -> bool:
    # Initiate new groups
    try:
        gid = message.chat.id
        text = get_debug_text(client, message.chat)
        invited_by = message.from_user.id
        # Check permission
        if invited_by == glovar.user_id:
            # Remove the left status
            if gid in glovar.left_group_ids:
                glovar.left_group_ids.discard(gid)

            # Update group's admin list
            if init_group_id(gid):
                admin_members = get_admins(client, gid)
                if admin_members:
                    glovar.admin_ids[gid] = {admin.user.id for admin in admin_members
                                             if not admin.user.is_bot and not admin.user.is_deleted}
                    save("admin_ids")
                    text += f"状态：{code('已加入群组')}\n"
                else:
                    thread(leave_group, (client, gid))
                    text += (f"状态：{code('已退出群组')}\n"
                             f"原因：{code('获取管理员列表失败')}\n")
        else:
            if gid in glovar.left_group_ids:
                return leave_group(client, gid)

            leave_group(client, gid)
            text += (f"状态：{code('已退出群组')}\n"
                     f"原因：{code('未授权使用')}\n")
            if message.from_user.username:
                text += f"邀请人：{user_mention(invited_by)}\n"
            else:
                text += f"邀请人：{code(invited_by)}\n"

        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Init group error: {e}", exc_info=True)

    return False


@Client.on_message(Filters.incoming & Filters.channel & exchange_channel
                   & ~Filters.command(glovar.all_commands, glovar.prefix))
def process_data(client: Client, message: Message) -> bool:
    # Process the data in exchange channel
    try:
        data = receive_text_data(message)
        if data:
            sender = data["from"]
            receivers = data["to"]
            action = data["action"]
            action_type = data["type"]
            data = data["data"]
            # This will look awkward,
            # seems like it can be simplified,
            # but this is to ensure that the permissions are clear,
            # so it is intentionally written like this
            if glovar.sender in receivers:

                if sender == "AVATAR":

                    if action == "update":
                        if action_type == "avatar":
                            receive_avatar(client, message, data)

                elif sender == "CAPTCHA":

                    if action == "update":
                        if action_type == "score":
                            receive_user_score(client, sender, data)

                elif sender == "CONFIG":

                    if action == "config":
                        if action_type == "commit":
                            receive_config_commit(data)
                        elif action_type == "reply":
                            receive_config_reply(client, data)

                elif sender == "CLEAN":

                    if action == "add":
                        if action_type == "bad":
                            receive_add_bad(client, sender, data)
                        elif action_type == "watch":
                            receive_watch_user(data)

                    elif action == "update":
                        if action_type == "declare":
                            receive_declared_message(data)
                        elif action_type == "score":
                            receive_user_score(client, sender, data)

                elif sender == "LANG":

                    if action == "add":
                        if action_type == "bad":
                            receive_add_bad(client, sender, data)
                        elif action_type == "watch":
                            receive_watch_user(data)

                    elif action == "update":
                        if action_type == "declare":
                            receive_declared_message(data)
                        elif action_type == "score":
                            receive_user_score(client, sender, data)

                elif sender == "LONG":

                    if action == "add":
                        if action_type == "bad":
                            receive_add_bad(client, sender, data)
                        elif action_type == "watch":
                            receive_watch_user(data)

                    elif action == "update":
                        if action_type == "declare":
                            receive_declared_message(data)
                        elif action_type == "score":
                            receive_user_score(client, sender, data)

                elif sender == "MANAGE":

                    if action == "add":
                        if action_type == "bad":
                            receive_add_bad(client, sender, data)
                        elif action_type == "except":
                            receive_add_except(client, data)

                    elif action == "leave":
                        if action_type == "approve":
                            receive_leave_approve(client, data)

                    elif action == "remove":
                        if action_type == "bad":
                            receive_remove_bad(client, sender, data)
                        elif action_type == "except":
                            receive_remove_except(client, data)
                        elif action_type == "score":
                            receive_remove_score(data)
                        elif action_type == "watch":
                            receive_remove_watch(data)

                    elif action == "status":
                        if action_type == "ask":
                            receive_status_ask(client, data)

                    elif action == "update":
                        if action_type == "refresh":
                            receive_refresh(client, data)

                elif sender == "NOFLOOD":

                    if action == "add":
                        if action_type == "bad":
                            receive_add_bad(client, sender, data)
                        elif action_type == "watch":
                            receive_watch_user(data)

                    elif action == "update":
                        if action_type == "declare":
                            receive_declared_message(data)
                        elif action_type == "score":
                            receive_user_score(client, sender, data)

                elif sender == "NOPORN":

                    if action == "add":
                        if action_type == "bad":
                            receive_add_bad(client, sender, data)
                        elif action_type == "watch":
                            receive_watch_user(data)

                    elif action == "update":
                        if action_type == "declare":
                            receive_declared_message(data)
                        elif action_type == "score":
                            receive_user_score(client, sender, data)

                elif sender == "RECHECK":

                    if action == "add":
                        if action_type == "bad":
                            receive_add_bad(client, sender, data)
                        elif action_type == "watch":
                            receive_watch_user(data)

                    elif action == "update":
                        if action_type == "declare":
                            receive_declared_message(data)
                        elif action_type == "score":
                            receive_user_score(client, sender, data)

                elif sender == "REGEX":

                    if action == "regex":
                        if action_type == "update":
                            receive_regex(client, message, data)
                        elif action_type == "count":
                            if data == "ask":
                                send_count(client)

                elif sender == "USER":

                    if action == "remove":
                        if action_type == "bad":
                            receive_remove_bad(client, sender, data)

                    elif action == "update":
                        if action_type == "preview":
                            receive_preview(client, message, data)

                elif sender == "WARN":

                    if action == "update":
                        if action_type == "score":
                            receive_user_score(client, sender, data)

                    elif action == "help":
                        if action_type == "list":
                            receive_report_ids(client, message, data)

                elif sender == "WATCH":

                    if action == "add":
                        if action_type == "watch":
                            receive_watch_user(data)

        return True
    except Exception as e:
        logger.warning(f"Process data error: {e}", exc_info=True)

    return False


@Client.on_message(Filters.incoming & Filters.group & test_group & from_user & ~Filters.service
                   & ~Filters.command(glovar.all_commands, glovar.prefix))
def test(client: Client, message: Message) -> bool:
    # Show test results in TEST group
    if glovar.locks["test"].acquire():
        try:
            nospam_test(client, message)

            return True
        except Exception as e:
            logger.warning(f"Test error: {e}", exc_info=True)
        finally:
            glovar.locks["test"].release()

    return False
