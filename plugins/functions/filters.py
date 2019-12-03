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
import re
from copy import deepcopy
from string import ascii_lowercase
from typing import Match, Optional, Union

from pyrogram import CallbackQuery, Client, Filters, Message, User

from .. import glovar
from .channel import get_content
from .etc import get_channel_link, get_filename, get_entity_text, get_forward_name, get_full_name, get_md5sum, get_now
from .etc import get_links, get_stripped_link, get_text, thread
from .file import delete_file, get_downloaded_path, save
from .group import get_description, get_group_sticker, get_member, get_pinned
from .ids import init_group_id
from .image import get_color, get_file_id, get_ocr, get_qrcode
from .telegram import get_sticker_title, resolve_username

# Enable logging
logger = logging.getLogger(__name__)


def is_authorized_group(_, update: Union[CallbackQuery, Message]) -> bool:
    # Check if the message is send from the authorized group
    try:
        if isinstance(update, CallbackQuery):
            message = update.message
        else:
            message = update

        if not message.chat:
            return False

        cid = message.chat.id
        if init_group_id(cid):
            return True
    except Exception as e:
        logger.warning(f"Is authorized group error: {e}", exc_info=True)

    return False


def is_class_c(_, message: Message) -> bool:
    # Check if the message is sent from Class C personnel
    try:
        if not message.from_user:
            return False

        # Basic data
        uid = message.from_user.id
        gid = message.chat.id

        # Check permission
        if uid in glovar.admin_ids[gid] or uid in glovar.bot_ids or message.from_user.is_self:
            return True
    except Exception as e:
        logger.warning(f"Is class c error: {e}", exc_info=True)

    return False


def is_class_d(_, message: Message) -> bool:
    # Check if the message is Class D object
    try:
        if message.from_user:
            if is_class_d_user(message.from_user):
                return True

        if message.forward_from:
            fid = message.forward_from.id
            if fid in glovar.bad_ids["users"]:
                return True

        if message.forward_from_chat:
            cid = message.forward_from_chat.id
            if cid in glovar.bad_ids["channels"]:
                return True
    except Exception as e:
        logger.warning(f"Is class d error: {e}", exc_info=True)

    return False


def is_class_e(_, message: Message, test: bool = False) -> bool:
    # Check if the message is Class E object
    try:
        if message.from_user and not test:
            if is_class_e_user(message.from_user):
                return True

        if message.forward_from_chat:
            cid = message.forward_from_chat.id
            if cid in glovar.except_ids["channels"]:
                return True

        if message.game:
            short_name = message.game.short_name
            if short_name in glovar.except_ids["long"]:
                return True

        content = get_content(message)

        if not content:
            return False

        if (content in glovar.except_ids["long"]
                or content in glovar.except_ids["temp"]):
            return True
    except Exception as e:
        logger.warning(f"Is class e error: {e}", exc_info=True)

    return False


def is_declared_message(_, message: Message) -> bool:
    # Check if the message is declared by other bots
    try:
        if not message.chat:
            return False

        gid = message.chat.id
        mid = message.message_id
        return is_declared_message_id(gid, mid)
    except Exception as e:
        logger.warning(f"Is declared message error: {e}", exc_info=True)

    return False


def is_exchange_channel(_, message: Message) -> bool:
    # Check if the message is sent from the exchange channel
    try:
        if not message.chat:
            return False

        cid = message.chat.id
        if glovar.should_hide:
            return cid == glovar.hide_channel_id
        else:
            return cid == glovar.exchange_channel_id
    except Exception as e:
        logger.warning(f"Is exchange channel error: {e}", exc_info=True)

    return False


def is_from_user(_, message: Message) -> bool:
    # Check if the message is sent from a user
    try:
        if message.from_user and message.from_user.id != 777000:
            return True
    except Exception as e:
        logger.warning(f"Is from user error: {e}", exc_info=True)

    return False


def is_hide_channel(_, message: Message) -> bool:
    # Check if the message is sent from the hide channel
    try:
        if not message.chat:
            return False

        cid = message.chat.id
        if cid == glovar.hide_channel_id:
            return True
    except Exception as e:
        logger.warning(f"Is hide channel error: {e}", exc_info=True)

    return False


def is_new_group(_, message: Message) -> bool:
    # Check if the bot joined a new group
    try:
        new_users = message.new_chat_members
        if new_users:
            return any(user.is_self for user in new_users)
        elif message.group_chat_created or message.supergroup_chat_created:
            return True
    except Exception as e:
        logger.warning(f"Is new group error: {e}", exc_info=True)

    return False


def is_test_group(_, update: Union[CallbackQuery, Message]) -> bool:
    # Check if the message is sent from the test group
    try:
        if isinstance(update, CallbackQuery):
            message = update.message
        else:
            message = update

        if not message.chat:
            return False

        cid = message.chat.id
        if cid == glovar.test_group_id:
            return True
    except Exception as e:
        logger.warning(f"Is test group error: {e}", exc_info=True)

    return False


authorized_group = Filters.create(
    func=is_authorized_group,
    name="Authorized Group"
)

class_c = Filters.create(
    func=is_class_c,
    name="Class C"
)

class_d = Filters.create(
    func=is_class_d,
    name="Class D"
)

class_e = Filters.create(
    func=is_class_e,
    name="Class E"
)

declared_message = Filters.create(
    func=is_declared_message,
    name="Declared message"
)

exchange_channel = Filters.create(
    func=is_exchange_channel,
    name="Exchange Channel"
)

from_user = Filters.create(
    func=is_from_user,
    name="From User"
)

hide_channel = Filters.create(
    func=is_hide_channel,
    name="Hide Channel"
)

new_group = Filters.create(
    func=is_new_group,
    name="New Group"
)

test_group = Filters.create(
    func=is_test_group,
    name="Test Group"
)


def is_ad_text(text: str, ocr: bool, matched: str = "") -> str:
    # Check if the text is ad text
    try:
        if not text:
            return ""

        for c in ascii_lowercase:
            if c != matched and is_regex_text(f"ad{c}", text, ocr):
                return c
    except Exception as e:
        logger.warning(f"Is ad text error: {e}", exc_info=True)

    return ""


def is_avatar_image(path: str) -> bool:
    # Check if the image is avatar image
    try:
        # Check QR code
        qrcode = get_qrcode(path)
        if qrcode:
            if is_regex_text("ava", qrcode) or is_ban_text(qrcode, False):
                return True

        # Check OCR
        ocr = get_ocr(path)
        if ocr:
            if is_regex_text("ava", ocr, True) or is_ban_text(ocr, True):
                return True
    except Exception as e:
        logger.warning(f"Is avatar image error: {e}", exc_info=True)

    return False


def is_bad_message(client: Client, message: Message, text: str = None, image_path: str = None) -> str:
    # Check if the message is bad message
    if image_path:
        need_delete = [image_path]
    else:
        need_delete = []

    try:
        if not message.chat:
            return ""

        # Basic data
        gid = message.chat.id
        now = message.date or get_now()

        # Regular message
        if not (text or image_path):
            # Check detected records

            # If the user is being punished
            if is_detected_user(message):
                return "true"

            # Content
            message_content = get_content(message)
            wb_user = is_watch_user(message.from_user, "ban", now)
            score_user = is_high_score_user(message.from_user)
            wd_user = is_watch_user(message.from_user, "delete", now)
            limited_user = is_limited_user(gid, message.from_user, now, glovar.configs[gid].get("new"))

            if message_content:
                detection = glovar.contents.get(message_content, "")
                if detection == "ban":
                    return detection

                if (wb_user or score_user) and detection == "wb":
                    return detection

                if detection == "del":
                    return detection

                if (wb_user or score_user or wd_user or limited_user) and detection == "wd":
                    return detection

                if message_content in glovar.bad_ids["contents"]:
                    return "del content"

            # Url
            detected_url = is_detected_url(message)

            if detected_url == "ban":
                return detected_url

            if (wb_user or score_user) and detected_url == "wb":
                return detected_url

            if detected_url == "del":
                return detected_url

            if (wb_user or score_user or wd_user or limited_user) and detected_url == "wd":
                return detected_url

            # Start detect ban

            # Check the forward from name
            forward_name = get_forward_name(message, True)

            if forward_name and forward_name not in glovar.except_ids["long"]:
                if forward_name in glovar.bad_ids["contents"]:
                    return "ban name content"

                if is_nm_text(forward_name):
                    return "ban name"

                if is_contact(forward_name):
                    return "ban name contact"

            # Check the user's name
            name = get_full_name(message.from_user, True)

            if name and name not in glovar.except_ids["long"]:
                if name in glovar.bad_ids["contents"]:
                    return "ban name content"

                if is_nm_text(name):
                    return "ban name"

                if is_contact(name):
                    return "ban name contact"

            # Bypass
            message_text = get_text(message)
            description = get_description(client, gid)
            if (description and message_text) and message_text in description:
                return ""

            pinned_message = get_pinned(client, gid)
            pinned_content = get_content(pinned_message)
            if (pinned_content and message_content) and message_content in pinned_content:
                return ""

            pinned_text = get_text(pinned_message)
            if (pinned_text and message_text) and message_text in pinned_text:
                return ""

            group_sticker = get_group_sticker(client, gid)
            if message.sticker:
                sticker_name = message.sticker.set_name
                if sticker_name == group_sticker:
                    return ""
            else:
                sticker_name = ""

            # Check the message's text
            message_text = get_text(message, True)
            if message_text:
                if is_ban_text(message_text, False):
                    return "ban"

            # Check the filename:
            file_name = get_filename(message, True)
            if file_name:
                if is_regex_text("fil", file_name) or is_ban_text(file_name, False):
                    return "ban"

            # Check image
            qrcode = ""
            ocr = ""
            all_text = ""

            # Get the image
            file_id, file_ref, big = get_file_id(message)
            image_path = big and get_downloaded_path(client, file_id, file_ref)
            image_path and need_delete.append(image_path)

            # Check declared status
            if is_declared_message(None, message):
                return ""

            # Check hash
            image_hash = image_path and get_md5sum("file", image_path)
            if image_path and image_hash and image_hash not in glovar.except_ids["temp"]:
                # Check declare status
                if is_declared_message(None, message):
                    return ""

                if big:
                    # Get QR code
                    qrcode = get_qrcode(image_path)
                    if qrcode:
                        if is_ban_text(qrcode, False):
                            return "ban"

                        if is_regex_text("ad", message_text) or is_ad_text(message_text, False):
                            return "ban"

                    # Get OCR
                    ocr = get_ocr(image_path)
                    if ocr:
                        message.new_chat_title = ocr
                        if is_ban_text(ocr, True):
                            return "ban"

                        if message_text:
                            all_text = message_text + ocr
                            message.new_chat_title = all_text
                            if is_ban_text(all_text, False):
                                return "ban"

            # Start detect watch ban

            if wb_user or score_user:
                # Check the message's text
                if message_text:
                    if is_wb_text(message_text, False):
                        return "wb"

                # Check channel restriction
                if is_restricted_channel(message):
                    return "wb"

                # Check the forward from name:
                if forward_name and forward_name not in glovar.except_ids["long"]:
                    if is_wb_text(forward_name, False):
                        return "wb name"

                # Check the document filename:
                if file_name:
                    if is_wb_text(file_name, False):
                        return "wb"

                # Check emoji
                if is_emoji("wb", message_text, message):
                    return "wb"

                # Check exe file
                if is_exe(message):
                    return "wb"

                # Check Telegram link
                if is_tgl(client, message, True):
                    return "wb"

                # Check image
                if qrcode:
                    return "wb"

                if ocr:
                    if is_wb_text(ocr, True):
                        return "wb"

                if all_text:
                    if is_wb_text(all_text, False):
                        return "wb"

            # Start detect delete

            # Check the message's text
            if message_text:
                if is_regex_text("del", message_text):
                    return "del"

            # Check the document filename:
            if file_name:
                if is_regex_text("del", file_name):
                    return "del"

            # Check image
            if qrcode:
                if is_regex_text("del", qrcode):
                    return "del"

            if ocr:
                if is_regex_text("del", ocr, True):
                    return "del"

            if all_text:
                if is_regex_text("del", all_text, True):
                    return "del"

                if is_contact(all_text):
                    return "del contact"

            # Check sticker
            if sticker_name:
                if sticker_name not in glovar.except_ids["long"]:
                    if is_regex_text("sti", sticker_name):
                        return f"del name {sticker_name}"

                sticker_title = get_sticker_title(client, sticker_name, True)
                if sticker_title not in glovar.except_ids["long"]:
                    if is_regex_text("sti", sticker_title):
                        return f"del name {sticker_title}"

            # Start detect watch delete

            if wb_user or score_user or wd_user or limited_user:
                # Some media type
                if (message.animation
                        or message.audio
                        or message.document
                        or message.game
                        or message.location
                        or message.venue
                        or message.via_bot
                        or message.video
                        or message.video_note):
                    return "wd"

                # Forwarded message
                if message.forward_from_chat:
                    return "wd"

                # Check the message's text
                if message_text:
                    if is_wd_text(message_text, False):
                        return "wd"

                # Check image
                if qrcode:
                    return "wd"

                if ocr:
                    if is_wd_text(ocr, True):
                        return "wd"

                if all_text:
                    if is_wd_text(all_text, False):
                        return "wd"

                color = image_path and get_color(image_path)
                if color:
                    return "wd"

            # Start detect bad

            # Check the message's text
            if message_text:
                if is_regex_text("bad", message_text):
                    return "bad"

        # Preview message
        else:
            # Start detect ban

            # Check the text
            if text:
                if is_ban_text(text, False):
                    return "ban"

            # Check image
            qrcode = ""
            ocr = ""
            all_text = ""

            if image_path:
                # Get QR code
                qrcode = get_qrcode(image_path)
                if qrcode:
                    if is_ban_text(qrcode, False):
                        return "ban"

                    if is_regex_text("ad", text) or is_ad_text(text, False):
                        return "ban"

                # Get OCR
                ocr = get_ocr(image_path)
                if ocr:
                    if is_ban_text(ocr, True):
                        return "ban"

                    if text:
                        all_text = text + ocr
                        if is_ban_text(all_text, False):
                            return "ban"

            # Start detect watch ban
            wb_user = is_watch_user(message.from_user, "ban", now)
            score_user = is_high_score_user(message.from_user)

            if wb_user or score_user:
                # Check the text
                if text:
                    if is_wb_text(text, False):
                        return "wb"

                # Check image
                if qrcode:
                    return "wb"

                if ocr:
                    if is_wb_text(ocr, True):
                        return "wb"

                if all_text:
                    if is_wb_text(all_text, False):
                        return "wb"

            # Start detect delete

            # Check the text
            if text:
                if is_regex_text("del", text):
                    return "del"

            # Check image
            if qrcode:
                if is_regex_text("del", qrcode):
                    return "del"

            if ocr:
                if is_regex_text("del", ocr, True):
                    return "del"

            if all_text:
                if is_regex_text("del", all_text, False):
                    return "del"

                if is_contact(all_text):
                    return "del contact"

            # Start detect watch delete

            wd_user = is_watch_user(message.from_user, "delete", now)
            limited_user = is_limited_user(gid, message.from_user, now, glovar.configs[gid].get("new"))

            if wb_user or score_user or wd_user or limited_user:
                # Check the text
                if text:
                    if is_wd_text(text, False):
                        return "wd"

                # Check image
                if qrcode:
                    return "wd"

                if ocr:
                    if is_wd_text(ocr, True):
                        return "wd"

                if all_text:
                    if is_wd_text(all_text, False):
                        return "wd"

                color = image_path and get_color(image_path)
                if color:
                    return "wd"

            # Start detect bad

            # Check the text
            if text:
                if is_regex_text("bad", text):
                    return "bad"
    except Exception as e:
        logger.warning(f"Is watch message error: {e}", exc_info=True)
    finally:
        for file in need_delete:
            thread(delete_file, (file,))

    return ""


def is_ban_text(text: str, ocr: bool, message: Message = None) -> bool:
    # Check if the text is ban text
    try:
        if is_regex_text("ban", text, ocr):
            return True

        # ad + con
        ad = is_regex_text("ad", text, ocr)
        con = is_con_text(text, ocr)

        if ad and con:
            return True

        # emoji + con
        emoji = is_emoji("ad", text, message)

        if emoji and con:
            return True

        # ad_ + con
        ad = is_ad_text(text, ocr)

        if ad and con:
            return True

        # ad_ + emoji
        if ad and emoji:
            return True

        # ad_ + ad_
        if ad:
            ad = is_ad_text(text, ocr, ad)
            return bool(ad)
    except Exception as e:
        logger.warning(f"Is ban text error: {e}", exc_info=True)

    return False


def is_bio_text(text: str) -> bool:
    # Check if the text is bio text
    try:
        if (is_regex_text("bio", text)
                or is_ban_text(text, False)):
            return True
    except Exception as e:
        logger.warning(f"Is bio text error: {e}", exc_info=True)

    return False


def is_class_d_user(user: Union[int, User]) -> bool:
    # Check if the user is a Class D personnel
    try:
        if isinstance(user, int):
            uid = user
        else:
            uid = user.id

        if uid in glovar.bad_ids["users"]:
            return True
    except Exception as e:
        logger.warning(f"Is class d user error: {e}", exc_info=True)

    return False


def is_class_e_user(user: Union[int, User]) -> bool:
    # Check if the user is a Class E personnel
    try:
        if isinstance(user, int):
            uid = user
        else:
            uid = user.id

        if uid in glovar.bot_ids:
            return True

        group_list = list(glovar.admin_ids)
        for gid in group_list:
            if uid in glovar.admin_ids.get(gid, set()):
                return True
    except Exception as e:
        logger.warning(f"Is class e user error: {e}", exc_info=True)

    return False


def is_con_text(text: str, ocr: bool) -> bool:
    # Check if the text is con text
    try:
        if (is_regex_text("con", text, ocr)
                or is_regex_text("iml", text, ocr)
                or is_regex_text("pho", text, ocr)):
            return True

        if is_contact(text):
            return True
    except Exception as e:
        logger.warning(f"Is con text error: {e}", exc_info=True)

    return False


def is_contact(text: str) -> str:
    # Check if the text contains bad contacts
    try:
        for contact in glovar.bad_ids["contacts"]:
            if re.search(contact, text, re.I):
                return contact
    except Exception as e:
        logger.warning(f"Is contact error: {e}", exc_info=True)

    return ""


def is_declared_message_id(gid: int, mid: int) -> bool:
    # Check if the message's ID is declared by other bots
    try:
        if mid in glovar.declared_message_ids.get(gid, set()):
            return True
    except Exception as e:
        logger.warning(f"Is declared message id error: {e}", exc_info=True)

    return False


def is_detected_url(message: Message) -> str:
    # Check if the message include detected url, return detected type
    try:
        if is_class_c(None, message):
            return ""

        links = get_links(message)
        for link in links:
            detected_type = glovar.contents.get(link, "")
            if detected_type:
                return detected_type
    except Exception as e:
        logger.warning(f"Is detected url error: {e}", exc_info=True)

    return ""


def is_detected_user(message: Message) -> bool:
    # Check if the message is sent by a detected user
    try:
        if not message.from_user:
            return False

        gid = message.chat.id
        uid = message.from_user.id
        now = message.date or get_now()
        return is_detected_user_id(gid, uid, now)
    except Exception as e:
        logger.warning(f"Is detected user error: {e}", exc_info=True)

    return False


def is_detected_user_id(gid: int, uid: int, now: int) -> bool:
    # Check if the user_id is detected in the group
    try:
        user_status = glovar.user_ids.get(uid, {})

        if not user_status:
            return False

        status = user_status["detected"].get(gid, 0)
        if now - status < glovar.time_punish:
            return True
    except Exception as e:
        logger.warning(f"Is detected user id error: {e}", exc_info=True)

    return False


def is_emoji(the_type: str, text: str, message: Message = None) -> bool:
    # Check the emoji type
    try:
        if message:
            text = get_text(message, False, False)

        emoji_dict = {}
        emoji_set = {emoji for emoji in glovar.emoji_set if emoji in text and emoji not in glovar.emoji_protect}
        emoji_old_set = deepcopy(emoji_set)

        for emoji in emoji_old_set:
            if any(emoji in emoji_old and emoji != emoji_old for emoji_old in emoji_old_set):
                emoji_set.discard(emoji)

        for emoji in emoji_set:
            emoji_dict[emoji] = text.count(emoji)

        # Check ad
        if the_type == "ad":
            if any(emoji_dict[emoji] >= glovar.emoji_ad_single for emoji in emoji_dict):
                return True

            if sum(emoji_dict.values()) >= glovar.emoji_ad_total:
                return True

        # Check many
        elif the_type == "many":
            if sum(emoji_dict.values()) >= glovar.emoji_many:
                return True

        # Check wb
        elif the_type == "wb":
            if any(emoji_dict[emoji] >= glovar.emoji_wb_single for emoji in emoji_dict):
                return True

            if sum(emoji_dict.values()) >= glovar.emoji_wb_total:
                return True
    except Exception as e:
        logger.warning(f"Is emoji error: {e}", exc_info=True)

    return False


def is_exe(message: Message) -> bool:
    # Check if the message contain a exe
    try:
        extensions = ["apk", "bat", "cmd", "com", "exe", "msi", "pif", "scr", "vbs"]
        if message.document:
            if message.document.file_name:
                file_name = message.document.file_name
                for file_type in extensions:
                    if re.search(f"[.]{file_type}$", file_name, re.I):
                        return True

            if message.document.mime_type:
                mime_type = message.document.mime_type
                if "application/x-ms" in mime_type or "executable" in mime_type:
                    return True

        extensions.remove("com")
        links = get_links(message)
        for link in links:
            for file_type in extensions:
                if re.search(f"[.]{file_type}$", link, re.I):
                    return True
    except Exception as e:
        logger.warning(f"Is exe error: {e}", exc_info=True)

    return False


def is_friend_username(client: Client, gid: int, username: str, friend: bool, friend_user: bool = False) -> bool:
    # Check if it is a friend username
    try:
        username = username.strip()
        if not username:
            return False

        if username[0] != "@":
            username = "@" + username

        if not re.search(r"\B@([a-z][0-9a-z_]{4,31})", username, re.I | re.M | re.S):
            return False

        peer_type, peer_id = resolve_username(client, username)
        if peer_type == "channel":
            if glovar.configs[gid].get("friend") or friend:
                if peer_id in glovar.except_ids["channels"] or glovar.admin_ids.get(peer_id, {}):
                    return True

        if peer_type == "user":
            if friend and friend_user:
                return True

            if friend or glovar.configs[gid].get("friend"):
                if is_class_e_user(peer_id):
                    return True

            member = get_member(client, gid, peer_id)
            if member and member.status in {"creator", "administrator", "member"}:
                return True
    except Exception as e:
        logger.warning(f"Is friend username: {e}", exc_info=True)

    return False


def is_high_score_user(user: User) -> float:
    # Check if the message is sent by a high score user
    try:
        if is_class_e_user(user):
            return 0.0

        uid = user.id
        user_status = glovar.user_ids.get(uid, {})

        if not user_status:
            return 0.0

        score = sum(user_status["score"].values())
        if score >= 3.0:
            return score
    except Exception as e:
        logger.warning(f"Is high score user error: {e}", exc_info=True)

    return 0.0


def is_limited_user(gid: int, user: User, now: int, short: bool = True) -> bool:
    # Check the user is limited
    try:
        if is_class_e_user(user):
            return False

        if glovar.configs[gid].get("new"):
            if is_new_user(user, now, gid):
                return True

        uid = user.id

        if not glovar.user_ids.get(uid, {}):
            return False

        if not glovar.user_ids[uid].get("join", {}):
            return False

        if is_high_score_user(user) >= 1.8:
            return True

        join = glovar.user_ids[uid]["join"].get(gid, 0)
        if short and now - join < glovar.time_short:
            return True

        track = [gid for gid in glovar.user_ids[uid]["join"]
                 if now - glovar.user_ids[uid]["join"][gid] < glovar.time_track]

        if len(track) >= glovar.limit_track:
            return True
    except Exception as e:
        logger.warning(f"Is limited user error: {e}", exc_info=True)

    return False


def is_new_user(user: User, now: int, gid: int = 0, joined: bool = False) -> bool:
    # Check if the message is sent from a new joined member
    try:
        if is_class_e_user(user):
            return False

        uid = user.id

        if not glovar.user_ids.get(uid, {}):
            return False

        if not glovar.user_ids[uid].get("join", {}):
            return False

        if joined:
            return True

        if gid:
            join = glovar.user_ids[uid]["join"].get(gid, 0)
            if now - join < glovar.time_new:
                return True
        else:
            for gid in list(glovar.user_ids[uid]["join"]):
                join = glovar.user_ids[uid]["join"].get(gid, 0)
                if now - join < glovar.time_new:
                    return True
    except Exception as e:
        logger.warning(f"Is new user error: {e}", exc_info=True)

    return False


def is_nm_text(text: str) -> bool:
    # Check if the text is nm text
    try:
        if (is_regex_text("nm", text)
                or is_regex_text("bio", text)
                or is_ban_text(text, False)):
            return True
    except Exception as e:
        logger.warning(f"Is nm text error: {e}", exc_info=True)

    return False


def is_old_user(client: Client, user: User, now: int, gid: int) -> bool:
    # Check if the user is old member
    try:
        if is_limited_user(gid, user, now, True):
            return False

        member = get_member(client, gid, user.id)
        if not member:
            return False

        joined = member.joined_date
        if now - joined > glovar.time_long:
            return True
    except Exception as e:
        logger.warning(f"Is old user error: {e}", exc_info=True)

    return False


def is_restricted_channel(message: Message) -> bool:
    # Check if the message is forwarded form restricted channel
    try:
        if not message.forward_from_chat:
            return False

        if message.forward_from_chat.restrictions:
            return True
    except Exception as e:
        logger.warning(f"Is restricted channel error: {e}", exc_info=True)

    return False


def is_regex_text(word_type: str, text: str, ocr: bool = False, again: bool = False) -> Optional[Match]:
    # Check if the text hit the regex rules
    result = None
    try:
        if text:
            if not again:
                text = re.sub(r"\s{2,}", " ", text)
            elif " " in text:
                text = re.sub(r"\s", "", text)
            else:
                return None
        else:
            return None

        with glovar.locks["regex"]:
            words = list(eval(f"glovar.{word_type}_words"))

        for word in words:
            if ocr and "(?# nocr)" in word:
                continue

            result = re.search(word, text, re.I | re.S | re.M)

            # Count and return
            if result:
                count = eval(f"glovar.{word_type}_words").get(word, 0)
                count += 1
                eval(f"glovar.{word_type}_words")[word] = count
                save(f"{word_type}_words")
                return result

        # Try again
        return is_regex_text(word_type, text, ocr, True)
    except Exception as e:
        logger.warning(f"Is regex text error: {e}", exc_info=True)

    return result


def is_tgl(client: Client, message: Message, friend: bool = False) -> bool:
    # Check if the message includes the Telegram link
    try:
        # Bypass prepare
        gid = message.chat.id
        description = get_description(client, gid).lower()
        pinned_message = get_pinned(client, gid)
        pinned_text = get_text(pinned_message).lower()

        # Check links
        bypass = get_stripped_link(get_channel_link(message))
        links = get_links(message)
        tg_links = [l.lower() for l in links if is_regex_text("tgl", l)]

        # Define a bypass link filter function
        def is_bypass_link(link: str) -> bool:
            try:
                link_username = re.match(r"t\.me/([a-z][0-9a-z_]{4,31})/", f"{link}/")
                if link_username:
                    link_username = link_username.group(1).lower()

                    if link_username in glovar.invalid:
                        return True

                    if link_username == "joinchat":
                        link_username = ""
                    else:
                        if is_friend_username(client, gid, link_username, friend):
                            return True

                if (f"{bypass}/" in f"{link}/"
                        or link in description
                        or (link_username and link_username in description)
                        or link in pinned_text
                        or (link_username and link_username in pinned_text)):
                    return True
            except Exception as ee:
                logger.warning(f"Is bypass link error: {ee}", exc_info=True)

            return False

        bypass_list = [link for link in tg_links if is_bypass_link(link)]
        if len(bypass_list) != len(tg_links):
            return True

        # Check text
        message_text = get_text(message, True).lower()
        for bypass in bypass_list:
            message_text = message_text.replace(bypass, "")

        if is_regex_text("tgl", message_text):
            return True

        # Check mentions
        entities = message.entities or message.caption_entities
        if not entities:
            return False

        for en in entities:
            if en.type == "mention":
                username = get_entity_text(message, en)[1:].lower()

                if username in glovar.invalid:
                    continue

                if message.chat.username and username == message.chat.username.lower():
                    continue

                if username in description:
                    continue

                if username in pinned_text:
                    continue

                if not is_friend_username(client, gid, username, friend):
                    return True

            if en.type == "user":
                uid = en.user.id
                member = get_member(client, gid, uid)
                if member is False:
                    return True

                if member and member.status not in {"creator", "administrator", "member"}:
                    return True
    except Exception as e:
        logger.warning(f"Is tgl error: {e}", exc_info=True)

    return False


def is_watch_user(user: User, the_type: str, now: int) -> bool:
    # Check if the message is sent by a watch user
    try:
        if is_class_e_user(user):
            return False

        uid = user.id
        until = glovar.watch_ids[the_type].get(uid, 0)
        if now < until:
            return True
    except Exception as e:
        logger.warning(f"Is watch user error: {e}", exc_info=True)

    return False


def is_wb_text(text: str, ocr: bool) -> bool:
    # Check if the text is wb text
    try:
        if (is_regex_text("wb", text, ocr)
                or is_regex_text("ad", text, ocr)
                or is_regex_text("iml", text, ocr)
                or is_regex_text("pho", text, ocr)
                or is_regex_text("sho", text, ocr)
                or is_regex_text("spc", text, ocr)):
            return True

        for c in ascii_lowercase:
            if c not in {"i"} and is_regex_text(f"ad{c}", text, ocr):
                return True
    except Exception as e:
        logger.warning(f"Is wb text error: {e}", exc_info=True)

    return False


def is_wd_text(text: str, ocr: bool) -> bool:
    # Check if the text is wd text
    try:
        if (is_regex_text("wd", text, ocr)
                or is_regex_text("adi", text, ocr)
                or is_regex_text("con", text, ocr)
                or is_regex_text("spe", text, ocr)
                or is_regex_text("tgp", text, ocr)):
            return True
    except Exception as e:
        logger.warning(f"Is wd text error: {e}", exc_info=True)

    return False
