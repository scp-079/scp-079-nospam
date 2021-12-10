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
from json import dumps
from typing import List, Optional, Set, Union

from pyrogram import Client
from pyrogram.types import Chat, Message, User

from .. import glovar
from .etc import code, code_block, general_link, get_forward_name, get_full_name, get_md5sum, get_text, lang
from .etc import message_link, thread
from .file import crypt_file, data_to_file, delete_file, get_new_path, save
from .image import get_file_id
from .telegram import forward_or_copy_message, get_group_info, send_document, send_message

# Enable logging
logger = logging.getLogger(__name__)


def ask_for_help(client: Client, level: str, gid: int, uid: int, group: str = "single") -> bool:
    # Let USER help to delete all message from user, or ban user globally
    try:
        data = {
            "group_id": gid,
            "user_id": uid
        }

        if level == "ban":
            data["type"] = (glovar.configs[gid].get("restrict") and "restrict") or "ban"
        elif level == "delete":
            data["type"] = group

        data["delete"] = glovar.configs[gid].get("delete")

        share_data(
            client=client,
            receivers=["USER"],
            action="help",
            action_type=level,
            data=data
        )

        return True
    except Exception as e:
        logger.warning(f"Ask for help error: {e}", exc_info=True)

    return False


def ask_help_captcha(client: Client, gid: int, uid: int, mid: int = None) -> bool:
    # Ask help captcha
    try:
        share_data(
            client=client,
            receivers=["CAPTCHA"],
            action="help",
            action_type="captcha",
            data={
                "group_id": gid,
                "user_id": uid,
                "message_id": mid
            }
        )
    except Exception as e:
        logger.warning(f"Ask help captcha error: {e}", exc_info=True)

    return False


def auto_report(client: Client, message: Message = None, gid: int = 0, uid: int = 0, mid: int = 0) -> bool:
    # Let WARN auto report a user
    try:
        # Basic data
        if message:
            gid = message.chat.id
            uid = message.from_user.id
            mid = message.message_id

        share_data(
            client=client,
            receivers=["WARN"],
            action="help",
            action_type="report",
            data={
                "group_id": gid,
                "user_id": uid,
                "message_id": mid
            }
        )
    except Exception as e:
        logger.warning(f"Auto report error: {e}", exc_info=True)

    return False


def declare_message(client: Client, gid: int, mid: int) -> bool:
    # Declare a message
    try:
        glovar.declared_message_ids[gid].add(mid)
        share_data(
            client=client,
            receivers=glovar.receivers["declare"],
            action="update",
            action_type="declare",
            data={
                "group_id": gid,
                "message_id": mid
            }
        )

        return True
    except Exception as e:
        logger.warning(f"Declare message error: {e}", exc_info=True)

    return False


def exchange_to_hide(client: Client) -> bool:
    # Let other bots exchange data in the hide channel instead
    try:
        glovar.should_hide = True
        share_data(
            client=client,
            receivers=["EMERGENCY"],
            action="backup",
            action_type="hide",
            data=True
        )

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{code(glovar.sender)}\n"
                f"{lang('issue')}{lang('colon')}{code(lang('exchange_invalid'))}\n"
                f"{lang('auto_fix')}{lang('colon')}{code(lang('protocol_1'))}\n")
        thread(send_message, (client, glovar.critical_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Exchange to hide error: {e}", exc_info=True)

    return False


def format_data(sender: str, receivers: List[str], action: str, action_type: str,
                data: Union[bool, dict, int, str] = None) -> str:
    # Get exchange string
    text = ""
    try:
        data = {
            "from": sender,
            "to": receivers,
            "action": action,
            "type": action_type,
            "data": data
        }
        text = code_block(dumps(data, indent=4))
    except Exception as e:
        logger.warning(f"Format data error: {e}", exc_info=True)

    return text


def forward_evidence(client: Client, message: Message, user: User, level: str, rule: str,
                     score: float = 0.0, contacts: Set[str] = None,
                     more: str = None, general: bool = True) -> Optional[Union[bool, Message]]:
    # Forward the message to the logging channel as evidence
    result = None
    try:
        # Get channel id
        channel_id = glovar.logging_channel_id if general else glovar.nospam_channel_id

        if not channel_id:
            channel_id = glovar.logging_channel_id

        # Basic information
        uid = user.id
        text = (f"{lang('project')}{lang('colon')}{code(glovar.sender)}\n"
                f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                f"{lang('level')}{lang('colon')}{code(level)}\n"
                f"{lang('rule')}{lang('colon')}{code(rule)}\n")

        # Additional information
        if message.game:
            text += f"{lang('message_type')}{lang('colon')}{code(lang('gam'))}\n"
        elif message.service:
            text += f"{lang('message_type')}{lang('colon')}{code(lang('ser'))}\n"

        if message.game:
            text += f"{lang('message_game')}{lang('colon')}{code(message.game.short_name)}\n"

        if lang("score") in rule:
            text += f"{lang('user_score')}{lang('colon')}{code(f'{score:.1f}')}\n"

        if lang("nick") in rule or lang("name") in rule:
            name = get_full_name(user)

            if name:
                text += f"{lang('user_name')}{lang('colon')}{code(name)}\n"

        if lang("username") in rule:
            username = message.from_user and message.from_user.username

            if username:
                text += f"{lang('more')}{lang('colon')}{code(username)}\n"

        if lang("bio") in rule:
            text += f"{lang('user_bio')}{lang('colon')}{code(more)}\n"

        if lang("from") in rule or lang("name") in rule:
            forward_name = get_forward_name(message)

            if forward_name:
                text += f"{lang('from_name')}{lang('colon')}{code(forward_name)}\n"

        if contacts:
            for contact in contacts:
                text += f"{lang('contact')}{lang('colon')}{code(contact)}\n"

        # Extra information
        if message.contact or message.location or message.venue or message.video_note or message.voice:
            text += f"{lang('more')}{lang('colon')}{code(lang('privacy'))}\n"
        elif message.game or message.service:
            text += f"{lang('more')}{lang('colon')}{code(lang('cannot_forward'))}\n"
        elif more:
            text += f"{lang('more')}{lang('colon')}{code(more)}\n"

        # DO NOT try to forward these types of message
        if (message.contact
                or message.location
                or message.venue
                or message.video_note
                or message.voice
                or message.game
                or message.service):
            result = send_message(client, channel_id, text)
            return result

        result = forward_or_copy_message(client, channel_id, message.chat.id, message.message_id)

        if not result:
            logger.warning(f"Can't save evidence {message.message_id} in {message.chat.id}")
            return False

        result = result.message_id
        result = send_message(client, channel_id, text, result)
    except Exception as e:
        logger.warning(f"Forward evidence error: {e}", exc_info=True)

    return result


def get_content(message: Message) -> str:
    # Get the message that will be added to lists, return the file_id and text's hash
    result = ""
    try:
        if not message:
            return ""

        file_id, _ = get_file_id(message)
        text = get_text(message)

        if file_id:
            result += file_id

        if message.audio:
            result += message.audio.file_id

        if message.document:
            result += message.document.file_id

        if message.sticker and message.sticker.is_animated:
            result += message.sticker.file_id

        if text:
            result += get_md5sum("string", text)
    except Exception as e:
        logger.warning(f"Get content error: {e}", exc_info=True)

    return result


def get_debug_text(client: Client, context: Union[int, Chat, List[int]]) -> str:
    # Get a debug message text prefix
    text = ""
    try:
        # Prefix
        text = f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"

        # List of group ids
        if isinstance(context, list):
            for group_id in context:
                group_name, group_link = get_group_info(client, group_id)
                text += (f"{lang('group_name')}{lang('colon')}{general_link(group_name, group_link)}\n"
                         f"{lang('group_id')}{lang('colon')}{code(group_id)}\n")

        # One group
        else:
            # Get group id
            if isinstance(context, int):
                group_id = context
            else:
                group_id = context.id

            # Generate the group info text
            group_name, group_link = get_group_info(client, context)
            text += (f"{lang('group_name')}{lang('colon')}{general_link(group_name, group_link)}\n"
                     f"{lang('group_id')}{lang('colon')}{code(group_id)}\n")
    except Exception as e:
        logger.warning(f"Get debug text error: {e}", exc_info=True)

    return text


def send_debug(client: Client, chat: Chat, action: str, uid: int, mid: int, em: Message) -> bool:
    # Send the debug message
    try:
        text = get_debug_text(client, chat)
        text += (f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                 f"{lang('action')}{lang('colon')}{code(action)}\n"
                 f"{lang('triggered_by')}{lang('colon')}{general_link(mid, message_link(em))}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Send debug error: {e}", exc_info=True)

    return False


def share_bad_user(client: Client, uid: int) -> bool:
    # Share a bad user with other bots
    try:
        share_data(
            client=client,
            receivers=glovar.receivers["bad"],
            action="add",
            action_type="bad",
            data={
                "id": uid,
                "type": "user"
            }
        )

        return True
    except Exception as e:
        logger.warning(f"Share bad user error: {e}", exc_info=True)

    return False


def share_data(client: Client, receivers: List[str], action: str, action_type: str,
               data: Union[bool, dict, int, str] = None, file: str = None, encrypt: bool = True) -> bool:
    # Use this function to share data in the channel
    try:
        thread(
            target=share_data_thread,
            args=(client, receivers, action, action_type, data, file, encrypt)
        )

        return True
    except Exception as e:
        logger.warning(f"Share data error: {e}", exc_info=True)

    return False


def share_data_thread(client: Client, receivers: List[str], action: str, action_type: str,
                      data: Union[bool, dict, int, str] = None, file: str = None, encrypt: bool = True) -> bool:
    # Share data thread
    try:
        if glovar.sender in receivers:
            receivers.remove(glovar.sender)

        if not receivers:
            return True

        if glovar.should_hide:
            channel_id = glovar.hide_channel_id
        else:
            channel_id = glovar.exchange_channel_id

        if file:
            text = format_data(
                sender=glovar.sender,
                receivers=receivers,
                action=action,
                action_type=action_type,
                data=data
            )

            if encrypt:
                # Encrypt the file, save to the tmp directory
                file_path = get_new_path()
                crypt_file("encrypt", file, file_path)
            else:
                # Send directly
                file_path = file

            result = send_document(client, channel_id, file_path, text)

            # Delete the tmp file
            if result:
                for f in {file, file_path}:
                    f.startswith("tmp/") and thread(delete_file, (f,))
        else:
            text = format_data(
                sender=glovar.sender,
                receivers=receivers,
                action=action,
                action_type=action_type,
                data=data
            )
            result = send_message(client, channel_id, text)

        # Sending failed due to channel issue
        if result is False and not glovar.should_hide:
            # Use hide channel instead
            exchange_to_hide(client)
            thread(share_data, (client, receivers, action, action_type, data, file, encrypt))

        return True
    except Exception as e:
        logger.warning(f"Share data thread error: {e}", exc_info=True)

    return False


def share_regex_count(client: Client, word_type: str) -> bool:
    # Use this function to share regex count to REGEX
    try:
        if not glovar.regex.get(word_type):
            return True

        if not eval(f"glovar.{word_type}_words"):
            return True

        file = data_to_file(eval(f"glovar.{word_type}_words"))
        share_data(
            client=client,
            receivers=["REGEX"],
            action="regex",
            action_type="count",
            data=f"{word_type}_words",
            file=file
        )

        return True
    except Exception as e:
        logger.warning(f"Share regex update error: {e}", exc_info=True)

    return False


def update_score(client: Client, uid: int) -> bool:
    # Update a user's score, share it
    try:
        delete_count = len(glovar.user_ids[uid]["detected"])
        bad_count = sum(glovar.user_ids[uid]["bad"][gid] for gid in list(glovar.user_ids[uid]["bad"]))
        score = delete_count * 0.6 + bad_count * 0.1
        glovar.user_ids[uid]["score"][glovar.sender.lower()] = score
        save("user_ids")
        share_data(
            client=client,
            receivers=glovar.receivers["score"],
            action="update",
            action_type="score",
            data={
                "id": uid,
                "score": round(score, 1)
            }
        )

        return True
    except Exception as e:
        logger.warning(f"Update score error: {e}", exc_info=True)

    return False
