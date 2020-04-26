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

from pyrogram import Client, Filters, Message

from .. import glovar
from ..functions.channel import get_content, get_debug_text
from ..functions.etc import code, general_link, get_full_name, get_now, lang, mention_id, t2t, thread
from ..functions.file import save
from ..functions.filters import authorized_group, class_c, class_e, class_d, declared_message, exchange_channel
from ..functions.filters import from_user, hide_channel, is_bad_message, is_bio_text, is_contact, is_declared_message
from ..functions.filters import is_nm_text, is_regex_text, new_group, test_group
from ..functions.group import leave_group
from ..functions.ids import init_group_id, init_user_id
from ..functions.receive import receive_add_bad, receive_add_except, receive_avatar, receive_captcha_kicked_user
from ..functions.receive import receive_clear_data, receive_config_commit, receive_config_reply, receive_config_show
from ..functions.receive import receive_declared_message, receive_help_check, receive_leave_approve, receive_preview
from ..functions.receive import receive_regex, receive_refresh, receive_remove_bad, receive_remove_except
from ..functions.receive import receive_remove_score, receive_remove_watch, receive_rollback, receive_status_ask
from ..functions.receive import receive_text_data, receive_user_score, receive_watch_user
from ..functions.telegram import get_admins, get_user_full, send_message
from ..functions.tests import nospam_test
from ..functions.timers import backup_files, send_count
from ..functions.user import terminate_user

# Enable logging
logger = logging.getLogger(__name__)


@Client.on_message(Filters.incoming & Filters.group & ~Filters.new_chat_members
                   & ~test_group & authorized_group
                   & from_user & ~class_c & ~class_e & ~class_d
                   & ~declared_message)
def check(client: Client, message: Message) -> bool:
    # Check the messages sent from groups

    has_text = bool(message and (message.text or message.caption))

    if has_text:
        glovar.locks["text"].acquire()
    else:
        glovar.locks["message"].acquire()

    try:
        # Basic data
        gid = message.chat.id

        # Check declare status
        if is_declared_message(None, message):
            return True

        # Check bad message
        content = get_content(message)
        detection = is_bad_message(client, message)

        if detection:
            result = terminate_user(client, message, message.from_user, detection)

            if result and content and detection != "true":
                glovar.contents[content] = detection
        elif glovar.configs[gid].get("message") and glovar.configs[gid].get("sticker") and message.sticker:
            if content:
                glovar.except_ids["temp"].add(content)
                save("except_ids")

        return True
    except Exception as e:
        logger.warning(f"Check error: {e}", exc_info=True)
    finally:
        if has_text:
            glovar.locks["text"].release()
        else:
            glovar.locks["message"].release()

    return False


@Client.on_message(Filters.incoming & Filters.group & Filters.new_chat_members
                   & ~test_group & ~new_group & authorized_group
                   & from_user & ~class_c & ~class_e
                   & ~declared_message)
def check_join(client: Client, message: Message) -> bool:
    # Check new joined user
    glovar.locks["message"].acquire()
    try:
        # Basic data
        gid = message.chat.id
        now = message.date or get_now()

        for new in message.new_chat_members:
            # Basic data
            uid = new.id

            # Check if the user is Class D personnel
            if uid in glovar.bad_ids["users"]:
                continue

            # Check if the user is white user
            if uid in glovar.white_ids:
                continue

            # Check declare status
            if is_declared_message(None, message):
                return True

            # Init the user's status
            if not init_user_id(uid):
                continue

            # Check name
            if glovar.configs[gid].get("nick"):
                name = get_full_name(new)

                if name and name not in glovar.except_ids["long"]:
                    t2t_name = t2t(name, True, True)

                    if is_nm_text(t2t_name):
                        terminate_user(client, message, new, "ban nick")
                    elif name in glovar.bad_ids["contents"]:
                        terminate_user(client, message, new, "ban nick record")
                    elif is_contact(t2t_name):
                        terminate_user(client, message, new, "ban nick contact")
                    elif is_regex_text("wb", t2t_name) and is_regex_text("sho", t2t_name):
                        terminate_user(client, message, new, "ban nick")
                    elif is_regex_text("bad", t2t_name) or is_regex_text("sho", t2t_name):
                        terminate_user(client, message, new, "bad nick")

            # Check bio
            if glovar.configs[gid].get("bio"):
                user = get_user_full(client, uid)

                if not user or not user.about:
                    bio = ""
                else:
                    bio = t2t(user.about, True, True)

                if bio and bio not in glovar.except_ids["long"]:
                    if is_bio_text(bio):
                        terminate_user(client, message, new, f"ban bio {bio}")
                    elif user.about in glovar.bad_ids["contents"]:
                        terminate_user(client, message, new, f"ban bio {bio}")

            # Check bot
            if glovar.configs[gid].get("bot") and new.is_bot:
                terminate_user(client, message, new, "ban bot")

            # Update user's join status
            glovar.user_ids[uid]["join"][gid] = now
            save("user_ids")

        return True
    except Exception as e:
        logger.warning(f"Check join error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


@Client.on_message(Filters.incoming & Filters.channel & ~Filters.command(glovar.all_commands, glovar.prefix)
                   & hide_channel, group=-1)
def exchange_emergency(client: Client, message: Message) -> bool:
    # Sent emergency channel transfer request
    try:
        # Read basic information
        data = receive_text_data(message)

        if not data:
            return True

        sender = data["from"]
        receivers = data["to"]
        action = data["action"]
        action_type = data["type"]
        data = data["data"]

        if "EMERGENCY" not in receivers:
            return True

        if action != "backup":
            return True

        if action_type != "hide":
            return True

        if data is True:
            glovar.should_hide = data
        elif data is False and sender == "MANAGE":
            glovar.should_hide = data

        project_text = general_link(glovar.project_name, glovar.project_link)
        hide_text = (lambda x: lang("enabled") if x else "disabled")(glovar.should_hide)
        text = (f"{lang('project')}{lang('colon')}{project_text}\n"
                f"{lang('action')}{lang('colon')}{code(lang('transfer_channel'))}\n"
                f"{lang('emergency_channel')}{lang('colon')}{code(hide_text)}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Exchange emergency error: {e}", exc_info=True)

    return False


@Client.on_message(Filters.incoming & Filters.group
                   & (Filters.new_chat_members | Filters.group_chat_created | Filters.supergroup_chat_created)
                   & ~test_group & new_group
                   & from_user)
def init_group(client: Client, message: Message) -> bool:
    # Initiate new groups
    try:
        # Basic data
        gid = message.chat.id
        inviter = message.from_user

        # Text prefix
        text = get_debug_text(client, message.chat)

        # Check permission
        if inviter.id == glovar.user_id:
            # Remove the left status
            if gid in glovar.left_group_ids:
                glovar.left_group_ids.discard(gid)
                save("left_group_ids")

            # Update group's admin list
            if not init_group_id(gid):
                return True

            admin_members = get_admins(client, gid)

            if admin_members:
                # Admin list
                glovar.admin_ids[gid] = {admin.user.id for admin in admin_members
                                         if (((not admin.user.is_bot and not admin.user.is_deleted)
                                              and admin.can_delete_messages
                                              and admin.can_restrict_members)
                                             or admin.status == "creator"
                                             or admin.user.id in glovar.bot_ids)}
                save("admin_ids")

                # Trust list
                glovar.trust_ids[gid] = {admin.user.id for admin in admin_members
                                         if ((not admin.user.is_bot and not admin.user.is_deleted)
                                             or admin.user.id in glovar.bot_ids)}
                save("trust_ids")

                # Text
                text += f"{lang('status')}{lang('colon')}{code(lang('status_joined'))}\n"
            else:
                thread(leave_group, (client, gid))
                text += (f"{lang('status')}{lang('colon')}{code(lang('status_left'))}\n"
                         f"{lang('reason')}{lang('colon')}{code(lang('reason_admin'))}\n")
        else:
            if gid in glovar.left_group_ids:
                return leave_group(client, gid)

            leave_group(client, gid)

            text += (f"{lang('status')}{lang('colon')}{code(lang('status_left'))}\n"
                     f"{lang('reason')}{lang('colon')}{code(lang('reason_unauthorized'))}\n")

        # Add inviter info
        if message.from_user.username:
            text += f"{lang('inviter')}{lang('colon')}{mention_id(inviter.id)}\n"
        else:
            text += f"{lang('inviter')}{lang('colon')}{code(inviter.id)}\n"

        # Send debug message
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Init group error: {e}", exc_info=True)

    return False


@Client.on_message((Filters.incoming or glovar.aio) & Filters.channel
                   & ~Filters.command(glovar.all_commands, glovar.prefix)
                   & exchange_channel)
def process_data(client: Client, message: Message) -> bool:
    # Process the data in exchange channel
    glovar.locks["receive"].acquire()
    try:
        data = receive_text_data(message)

        if not data:
            return True

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
                        receive_user_score(client, sender, data, True)

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
                        receive_watch_user(client, data)

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
                        receive_watch_user(client, data)

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
                        receive_watch_user(client, data)

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

                elif action == "backup":
                    if action_type == "now":
                        thread(backup_files, (client,))
                    elif action_type == "rollback":
                        receive_rollback(client, message, data)

                elif action == "clear":
                    receive_clear_data(client, action_type, data)

                elif action == "config":
                    if action_type == "show":
                        receive_config_show(client, data)

                elif action == "leave":
                    if action_type == "approve":
                        receive_leave_approve(client, data)

                elif action == "remove":
                    if action_type == "bad":
                        receive_remove_bad(client, data)
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
                        receive_watch_user(client, data)

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
                        receive_watch_user(client, data)

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
                        receive_watch_user(client, data)

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

                if action == "add":
                    if action_type == "bad":
                        receive_add_bad(client, sender, data)

                elif action == "update":
                    if action_type == "preview":
                        receive_preview(client, message, data)

            elif sender == "WARN":

                if action == "update":
                    if action_type == "score":
                        receive_user_score(client, sender, data)

                elif action == "help":
                    if action_type == "check":
                        receive_help_check(client, message, data)

            elif sender == "WATCH":

                if action == "add":
                    if action_type == "watch":
                        receive_watch_user(client, data, True)

        elif "USER" in receivers:

            if sender == "CAPTCHA":

                if action == "help":
                    if action_type == "delete":
                        receive_captcha_kicked_user(data)

        return True
    except Exception as e:
        logger.warning(f"Process data error: {e}", exc_info=True)
    finally:
        glovar.locks["receive"].release()

    return False


@Client.on_message(Filters.incoming & Filters.group & ~Filters.service
                   & ~Filters.command(glovar.all_commands, glovar.prefix)
                   & test_group
                   & from_user)
def test(client: Client, message: Message) -> bool:
    # Show test results in TEST group
    glovar.locks["test"].acquire()
    try:
        nospam_test(client, message)

        return True
    except Exception as e:
        logger.warning(f"Test error: {e}", exc_info=True)
    finally:
        glovar.locks["test"].release()

    return False
