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
import re
from copy import deepcopy
from subprocess import run, PIPE

from pyrogram import Client, filters
from pyrogram.types import Message

from .. import glovar
from ..functions.channel import get_content, get_debug_text, share_data
from ..functions.etc import code, code_block, delay, general_link, get_command_context, get_command_type, get_int
from ..functions.etc import get_now, get_readable_time, lang, mention_id, thread
from ..functions.file import save
from ..functions.filters import authorized_group, from_user, is_bad_message, is_class_c, test_group
from ..functions.group import delete_message, get_config_text
from ..functions.telegram import get_group_info, send_message, send_report_message

# Enable logging
logger = logging.getLogger(__name__)


@Client.on_message(filters.incoming & filters.group & filters.command(["config"], glovar.prefix)
                   & ~test_group & authorized_group
                   & from_user)
def config(client: Client, message: Message) -> bool:
    # Request CONFIG session

    if not message or not message.chat:
        return True

    # Basic data
    gid = message.chat.id
    mid = message.message_id

    try:
        # Check permission
        if not is_class_c(None, message):
            return True

        # Check command format
        command_type = get_command_type(message)

        if not command_type or not re.search(f"^{glovar.sender}$", command_type, re.I):
            return True

        now = get_now()

        # Check the config lock
        if now - glovar.configs[gid]["lock"] < 310:
            return True

        # Set lock
        glovar.configs[gid]["lock"] = now
        save("configs")

        # Ask CONFIG generate a config session
        group_name, group_link = get_group_info(client, message.chat)
        share_data(
            client=client,
            receivers=["CONFIG"],
            action="config",
            action_type="ask",
            data={
                "project_name": glovar.project_name,
                "project_link": glovar.project_link,
                "group_id": gid,
                "group_name": group_name,
                "group_link": group_link,
                "user_id": message.from_user.id,
                "config": glovar.configs[gid],
                "default": glovar.default_config
            }
        )

        # Send debug message
        text = get_debug_text(client, message.chat)
        text += (f"{lang('admin_group')}{lang('colon')}{code(message.from_user.id)}\n"
                 f"{lang('action')}{lang('colon')}{code(lang('config_create'))}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Config error: {e}", exc_info=True)
    finally:
        if is_class_c(None, message):
            delay(3, delete_message, [client, gid, mid])
        else:
            delete_message(client, gid, mid)

    return False


@Client.on_message(filters.incoming & filters.group
                   & filters.command([f"config_{glovar.sender.lower()}"], glovar.prefix)
                   & ~test_group & authorized_group
                   & from_user)
def config_directly(client: Client, message: Message) -> bool:
    # Config the bot directly

    if not message or not message.chat:
        return True

    # Basic data
    gid = message.chat.id
    mid = message.message_id

    try:
        # Check permission
        if not is_class_c(None, message):
            return True

        aid = message.from_user.id
        success = True
        reason = lang("config_updated")
        new_config = deepcopy(glovar.configs[gid])
        text = f"{lang('admin_group')}{lang('colon')}{code(aid)}\n"

        # Check command format
        command_type, command_context = get_command_context(message)

        if command_type:
            if command_type == "show":
                text += f"{lang('action')}{lang('colon')}{code(lang('config_show'))}\n"
                text += get_config_text(new_config)
                thread(send_report_message, (30, client, gid, text))
                return True

            now = get_now()

            # Check the config lock
            if now - new_config["lock"] > 310:
                if command_type == "default":
                    new_config = deepcopy(glovar.default_config)
                else:
                    if command_context:
                        if command_type in {"delete", "restrict", "nick", "bio", "avatar", "message", "ocr", "sticker",
                                            "bot", "new", "deleter", "reporter", "scorer", "ml"}:
                            if command_context == "off":
                                new_config[command_type] = False
                            elif command_context == "on":
                                new_config[command_type] = True
                            else:
                                success = False
                                reason = lang("command_para")

                            if command_type == "deleter" and new_config[command_type]:
                                new_config["reporter"] = False
                            elif command_type == "reporter" and new_config[command_type]:
                                new_config["deleter"] = False
                        else:
                            success = False
                            reason = lang("command_type")
                    else:
                        success = False
                        reason = lang("command_lack")

                    if success:
                        new_config["default"] = False
            else:
                success = False
                reason = lang("config_locked")
        else:
            success = False
            reason = lang("command_usage")

        if success and new_config != glovar.configs[gid]:
            # Save new config
            glovar.configs[gid] = new_config
            save("configs")

            # Send debug message
            debug_text = get_debug_text(client, message.chat)
            debug_text += (f"{lang('admin_group')}{lang('colon')}{code(message.from_user.id)}\n"
                           f"{lang('action')}{lang('colon')}{code(lang('config_change'))}\n"
                           f"{lang('more')}{lang('colon')}{code(f'{command_type} {command_context}')}\n")
            thread(send_message, (client, glovar.debug_channel_id, debug_text))

        text += (f"{lang('action')}{lang('colon')}{code(lang('config_change'))}\n"
                 f"{lang('status')}{lang('colon')}{code(reason)}\n")
        thread(send_report_message, ((lambda x: 10 if x else 5)(success), client, gid, text))

        return True
    except Exception as e:
        logger.warning(f"Config directly error: {e}", exc_info=True)
    finally:
        delete_message(client, gid, mid)

    return False


@Client.on_message(filters.incoming & filters.group & filters.command(["content"], glovar.prefix)
                   & test_group
                   & from_user)
def content(client: Client, message: Message) -> bool:
    # Show message's content
    try:
        # Basic data
        cid = message.chat.id
        aid = message.from_user.id
        mid = message.message_id

        # Generate the report message
        text = f"{lang('admin')}{lang('colon')}{mention_id(aid)}\n\n"

        if message.reply_to_message:
            result = get_content(message.reply_to_message)

            if result:
                text += f"{lang('content')}{lang('colon')}" + "-" * 24 + "\n\n"
                text += code_block(result) + "\n"
            else:
                text += (f"{lang('status')}{lang('colon')}{code(lang('status_failed'))}\n"
                         f"{lang('reason')}{lang('colon')}{code(lang('reason_none'))}\n")
        else:
            text = (f"{lang('status')}{lang('colon')}{code(lang('status_failed'))}\n"
                    f"{lang('reason')}{lang('colon')}{code(lang('command_usage'))}\n")

        # Send the report message
        thread(send_message, (client, cid, text, mid))

        return True
    except Exception as e:
        logger.warning(f"Content error: {e}", exc_info=True)

    return False


@Client.on_message(filters.incoming & filters.group & filters.command(["nospam"], glovar.prefix)
                   & test_group
                   & from_user)
def nospam(client: Client, message: Message) -> bool:
    # Check message's detection
    try:
        # Basic data
        cid = message.chat.id
        aid = message.from_user.id
        mid = message.message_id

        # Generate the report message
        text = (f"{lang('admin')}{lang('colon')}{mention_id(aid)}\n\n"
                f"{lang('action')}{lang('colon')}{code(lang('spam_test'))}\n")

        if message.reply_to_message:
            result = is_bad_message(client, message.reply_to_message) or lang("reason_none")
            text += f"{lang('result')}{lang('colon')}{code(result)}\n"
        else:
            text = (f"{lang('status')}{lang('colon')}{code(lang('status_failed'))}\n"
                    f"{lang('reason')}{lang('colon')}{code(lang('command_usage'))}\n")

        # Send the report message
        thread(send_message, (client, cid, text, mid))

        return True
    except Exception as e:
        logger.warning(f"Nospam error: {e}", exc_info=True)

    return False


@Client.on_message(filters.incoming & filters.group & filters.command(["version"], glovar.prefix)
                   & test_group
                   & from_user)
def version(client: Client, message: Message) -> bool:
    # Check the program's version
    result = False

    try:
        # Basic data
        cid = message.chat.id
        aid = message.from_user.id
        mid = message.message_id

        # Get command type
        command_type = get_command_type(message)

        # Check the command type
        if command_type and command_type.upper() != glovar.sender:
            return False

        # Version info
        git_change = bool(run("git diff-index HEAD --", stdout=PIPE, shell=True).stdout.decode().strip())
        git_date = run("git log -1 --format='%at'", stdout=PIPE, shell=True).stdout.decode()
        git_date = get_readable_time(get_int(git_date), "%Y/%m/%d %H:%M:%S")
        git_hash = run("git rev-parse --short HEAD", stdout=PIPE, shell=True).stdout.decode()
        get_hash_link = f"https://github.com/scp-079/scp-079-{glovar.sender.lower()}/commit/{git_hash}"
        command_date = get_readable_time(message.date, "%Y/%m/%d %H:%M:%S")

        # Generate the text
        text = (f"{lang('admin')}{lang('colon')}{mention_id(aid)}\n\n"
                f"{lang('project')}{lang('colon')}{code(glovar.sender)}\n"
                f"{lang('version')}{lang('colon')}{code(glovar.version)}\n"
                f"{lang('本地修改')}{lang('colon')}{code(git_change)}\n"
                f"{lang('哈希值')}{lang('colon')}{general_link(git_hash, get_hash_link)}\n"
                f"{lang('提交时间')}{lang('colon')}{code(git_date)}\n"
                f"{lang('命令发送时间')}{lang('colon')}{code(command_date)}\n")

        # Send the report message
        result = send_message(client, cid, text, mid)
    except Exception as e:
        logger.warning(f"Version error: {e}", exc_info=True)

    return result
