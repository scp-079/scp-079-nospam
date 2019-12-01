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
from typing import Optional, Set, Union

from pyrogram import ChatPermissions, Client, Message, User

from .. import glovar
from .channel import ask_for_help, ask_help_captcha, auto_report, declare_message, forward_evidence, send_debug
from .channel import share_bad_user, update_score
from .etc import code, general_link, get_channel_link, get_forward_name, get_full_name, get_now, get_text, lang
from .etc import message_link, thread
from .file import save
from .group import delete_message
from .filters import is_class_d, is_declared_message, is_detected_user, is_friend_username, is_high_score_user
from .filters import is_limited_user, is_old_user, is_regex_text
from .ids import init_user_id
from .telegram import get_users, kick_chat_member, restrict_chat_member, send_message

# Enable logging
logger = logging.getLogger(__name__)


def add_bad_user(client: Client, uid: int) -> bool:
    # Add a bad user, share it
    try:
        if uid in glovar.bad_ids["users"]:
            return True

        glovar.bad_ids["users"].add(uid)
        save("bad_ids")
        share_bad_user(client, uid)

        return True
    except Exception as e:
        logger.warning(f"Add bad user error: {e}", exc_info=True)

    return False


def add_detected_user(gid: int, uid: int, now: int) -> bool:
    # Add or update a detected user's status
    try:
        if not init_user_id(uid):
            return False

        previous = glovar.user_ids[uid]["detected"].get(gid)
        glovar.user_ids[uid]["detected"][gid] = now

        return bool(previous)
    except Exception as e:
        logger.warning(f"Add detected user error: {e}", exc_info=True)

    return False


def ban_user(client: Client, gid: int, uid: Union[int, str]) -> bool:
    # Ban a user
    try:
        if glovar.configs[gid].get("restrict"):
            thread(restrict_chat_member, (client, gid, uid, ChatPermissions()))
        else:
            thread(kick_chat_member, (client, gid, uid))

        return True
    except Exception as e:
        logger.warning(f"Ban user error: {e}", exc_info=True)

    return False


def get_contacts(text: str) -> Set[str]:
    # Get the contacts information in the text
    result = set()
    try:
        for the_type in ["con", "iml", "pho"]:
            match = is_regex_text(the_type, text)

            if not match:
                continue

            for regex in eval(f"glovar.{the_type}_words"):
                if "?P<con>" not in regex:
                    continue

                sub_match = re.search(regex, text, re.I | re.M | re.S)
                if not sub_match:
                    continue

                group_dict = sub_match.groupdict()
                if not group_dict or not group_dict.get("con"):
                    continue

                result.add(group_dict["con"].lower())
                break
    except Exception as e:
        logger.warning(f"Get contact error: {e}", exc_info=True)

    return result


def get_user(client: Client, uid: Union[int, str]) -> Optional[User]:
    # Get a user
    result = None
    try:
        result = get_users(client, [uid])
        if result:
            result = result[0]
    except Exception as e:
        logger.warning(f"Get user error: {e}", exc_info=True)

    return result


def global_delete_score(client: Client, uid: int) -> bool:
    # Score global delete
    try:
        if uid in glovar.bad_ids["users"]:
            return True

        if not glovar.user_ids.get(uid) or not glovar.user_ids[uid].get("join"):
            return True

        total_score = sum(glovar.user_ids[uid]["score"].values())

        if total_score < 3.0:
            return True

        text = (f"{lang('project')}{lang('colon')}{code(glovar.sender)}\n"
                f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                f"{lang('level')}{lang('colon')}{code(lang('global_delete'))}\n"
                f"{lang('rule')}{lang('colon')}{code(lang('score_user'))}\n"
                f"{lang('user_score')}{lang('colon')}{code(total_score)}\n")
        result = send_message(client, glovar.logging_channel_id, text)

        if not result:
            return True

        gid = list(glovar.configs)[0]
        ask_for_help(client, "delete", gid, uid, "global")
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('global_delete'))}\n"
                f"{lang('evidence')}{lang('colon')}{general_link(result.message_id, message_link(result))}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Global delete score error: {e}", exc_info=True)

    return False


def global_delete_watch(client: Client, uid: int, mid: int) -> bool:
    # Watch global delete
    try:
        if uid in glovar.bad_ids["users"]:
            return True

        if not glovar.user_ids.get(uid) or not glovar.user_ids[uid].get("join"):
            return True

        text = (f"{lang('project')}{lang('colon')}{code(glovar.sender)}\n"
                f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                f"{lang('level')}{lang('colon')}{code(lang('global_delete'))}\n"
                f"{lang('rule')}{lang('colon')}{code(lang('watch_user'))}\n")
        result = send_message(client, glovar.logging_channel_id, text)

        if not result:
            return True

        gid = list(glovar.configs)[0]
        ask_for_help(client, "delete", gid, uid, "global")
        triggered_link = f"{get_channel_link(glovar.watch_channel_id)}/{mid}"
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('user_id')}{lang('colon')}{code(uid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('global_delete'))}\n"
                f"{lang('triggered_by')}{lang('colon')}{general_link(mid, triggered_link)}\n"
                f"{lang('evidence')}{lang('colon')}{general_link(result.message_id, message_link(result))}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Global delete watch error: {e}", exc_info=True)

    return False


def record_contacts_info(client: Client, text: str) -> Set[str]:
    # Record the contacts information in the message
    result = set()
    try:
        if not text.strip():
            return set()

        gid = list(glovar.configs)[0]
        contacts = get_contacts(text)

        for contact in contacts:
            if (contact
                    and contact not in glovar.bad_ids["contacts"]
                    and not is_friend_username(client, gid, contact, True)):
                glovar.bad_ids["contacts"].add(contact)
                save("bad_ids")

        result = contacts
    except Exception as e:
        logger.warning(f"Record contacts error: {e}", exc_info=True)

    return result


def remove_contacts_info(message: Message, text: str) -> bool:
    # Remove the contacts information
    try:
        # Extract contacts from report message in LOGGING
        if message:
            if not message.text:
                return True

            contacts = set()
            record_list = message.text.split("\n")

            for r in record_list:
                if re.search(f"^{lang('contact')}{lang('colon')}", r):
                    contacts.add(r.split(f"{lang('colon')}")[-1])

            if message.reply_to_message:
                forward_name = get_forward_name(message.reply_to_message, True)
                contacts = contacts | get_contacts(forward_name)
                message_text = get_text(message.reply_to_message, True)
                contacts = contacts | get_contacts(message_text)

        # Plain text as contact
        else:
            contacts = {text}

        # Remove the contacts
        for contact in contacts:
            if contact and contact in glovar.bad_ids["contacts"]:
                glovar.bad_ids["contacts"].discard(contact)
                save("bad_ids")
    except Exception as e:
        logger.warning(f"Remove contacts info error: {e}", exc_info=True)

    return False


def terminate_user(client: Client, message: Message, user: User, context: str) -> bool:
    # Delete user's message, or ban the user
    try:
        result = None

        # Check if it is necessary
        if is_class_d(None, message) or is_declared_message(None, message):
            return False

        gid = message.chat.id
        uid = user.id
        mid = message.message_id
        context_list = context.split()
        the_type = context_list[0]

        if len(context_list) >= 2:
            rule = context_list[1]
        else:
            rule = None

        if len(context_list) >= 3:
            more = " ".join(context_list[2:])
        else:
            more = None

        now = message.date or get_now()

        # Group config
        report_only = glovar.configs[gid].get("reporter")
        delete_only = glovar.configs[gid].get("deleter")

        # Bad message
        if the_type == "bad":
            # Basic info
            log_level = lang("score_auto")
            log_rule = lang("rule_global")
            debug_action = lang("score_micro")

            if rule == "name":
                log_rule = lang("name_examine")

            # Check if necessary
            if uid in glovar.recorded_ids[gid] and is_high_score_user(message.from_user):
                return False

            # Terminate
            result = forward_evidence(
                client=client,
                message=message,
                user=user,
                level=log_level,
                rule=log_rule,
                more=more
            )
            if result:
                if not init_user_id(uid):
                    return False
                glovar.user_ids[uid]["bad"][gid] = glovar.user_ids[uid]["bad"].get(gid, 0) + 1
                update_score(client, uid)
                if gid in glovar.report_ids and uid not in glovar.recorded_ids[gid]:
                    auto_report(client, message)
                glovar.recorded_ids[gid].add(uid)
                send_debug(
                    client=client,
                    chat=message.chat,
                    action=debug_action,
                    uid=uid,
                    mid=mid,
                    em=result
                )

        # Reporter
        elif report_only:
            # Basic info
            log_level = lang("score_auto")
            log_rule = lang("rule_custom")
            debug_action = lang("score_micro")

            if rule == "name":
                log_rule = lang("name_examine")

            # Check if necessary
            if uid in glovar.recorded_ids[gid] and is_high_score_user(message.from_user):
                return False

            # Terminate
            result = forward_evidence(
                client=client,
                message=message,
                user=user,
                level=log_level,
                rule=log_rule,
                more=more
            )
            if result:
                if not init_user_id(uid):
                    return False
                glovar.user_ids[uid]["bad"][gid] = glovar.user_ids[uid]["bad"].get(gid, 0) + 1
                update_score(client, uid)
                if gid in glovar.report_ids and uid not in glovar.recorded_ids[gid]:
                    auto_report(client, message)
                glovar.recorded_ids[gid].add(uid)
                send_debug(
                    client=client,
                    chat=message.chat,
                    action=debug_action,
                    uid=uid,
                    mid=mid,
                    em=result
                )

        # Delete the message
        elif the_type in {"del", "true"}:
            # Basic info
            log_level = lang("auto_delete")
            log_rule = lang("rule_global")
            debug_action = lang("auto_delete")

            if rule in {"contact", "content"}:
                log_rule = lang("record_message")
                debug_action = lang("record_delete")

            if more in {"contact", "content"}:
                log_rule = lang("record_message")
                debug_action = lang("record_delete")
                more = ""

            # Terminate
            if is_detected_user(message) or uid in glovar.recorded_ids[gid] or the_type == "true":
                delete_message(client, gid, mid)
                add_detected_user(gid, uid, now)
                declare_message(client, gid, mid)
            else:
                result = forward_evidence(
                    client=client,
                    message=message,
                    user=user,
                    level=log_level,
                    rule=log_rule,
                    more=more
                )
                if result:
                    glovar.recorded_ids[gid].add(uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    previous = add_detected_user(gid, uid, now)
                    not previous and update_score(client, uid)
                    send_debug(
                        client=client,
                        chat=message.chat,
                        action=debug_action,
                        uid=uid,
                        mid=mid,
                        em=result
                    )

        # Watch delete the message
        elif the_type == "wd":
            # Basic info
            log_level = lang("auto_delete")
            log_rule = lang("watch_user")
            debug_action = lang("watch_delete")
            score_user = is_high_score_user(message.from_user)
            limited_user = is_limited_user(gid, user, now, glovar.configs[gid].get("new"))

            if score_user:
                log_rule = lang("score_user")
                debug_action = lang("score_delete")
            elif limited_user and glovar.configs[gid].get("new"):
                log_rule = lang("limited_user")
                debug_action = lang("limited_delete")

            # Terminate
            if is_detected_user(message) or uid in glovar.recorded_ids[gid]:
                delete_message(client, gid, mid)
                add_detected_user(gid, uid, now)
                declare_message(client, gid, mid)
            else:
                result = forward_evidence(
                    client=client,
                    message=message,
                    user=user,
                    level=log_level,
                    rule=log_rule,
                    score=score_user,
                    more=more
                )
                if result:
                    glovar.recorded_ids[gid].add(uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    previous = add_detected_user(gid, uid, now)
                    not previous and update_score(client, uid)
                    send_debug(
                        client=client,
                        chat=message.chat,
                        action=debug_action,
                        uid=uid,
                        mid=mid,
                        em=result
                    )

        # Deleter
        elif delete_only:
            # Basic info
            log_level = lang("auto_delete")
            log_rule = lang("rule_custom")
            debug_action = lang("auto_delete")

            if rule == "name":
                log_rule = lang("name_examine")

            # Terminate
            if is_detected_user(message) or uid in glovar.recorded_ids[gid]:
                delete_message(client, gid, mid)
                add_detected_user(gid, uid, now)
                declare_message(client, gid, mid)
            else:
                result = forward_evidence(
                    client=client,
                    message=message,
                    user=user,
                    level=log_level,
                    rule=log_rule,
                    more=more
                )
                if result:
                    glovar.recorded_ids[gid].add(uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    previous = add_detected_user(gid, uid, now)
                    not previous and update_score(client, uid)
                    send_debug(
                        client=client,
                        chat=message.chat,
                        action=debug_action,
                        uid=uid,
                        mid=mid,
                        em=result
                    )

        # Watch ban the user
        elif the_type == "wb":
            # Basic info
            log_level = lang("auto_ban")
            log_rule = lang("watch_user")
            debug_action = lang("watch_ban")
            score_user = is_high_score_user(message.from_user)

            if score_user:
                log_rule = lang("score_user")
                debug_action = lang("score_ban")

            if rule == "name":
                log_rule = lang("name_watch")
                debug_action = lang("name_ban")
                if score_user:
                    log_rule = lang("name_score")

            # Terminate
            result = forward_evidence(
                client=client,
                message=message,
                user=user,
                level=log_level,
                rule=log_rule,
                score=score_user,
                more=more
            )
            if result:
                add_bad_user(client, uid)
                ban_user(client, gid, uid)
                delete_message(client, gid, mid)
                declare_message(client, gid, mid)
                ask_for_help(client, "ban", gid, uid)
                send_debug(
                    client=client,
                    chat=message.chat,
                    action=debug_action,
                    uid=uid,
                    mid=mid,
                    em=result
                )

        # Ban the user
        elif the_type == "ban":
            # Basic info
            log_level = lang("auto_ban")
            log_rule = lang("rule_global")
            debug_action = lang("auto_ban")

            # Terminate
            if rule == "bot":
                log_level = lang("auto_ban")
                log_rule = lang("rule_custom")
                debug_action = lang("bot")

                result = forward_evidence(
                    client=client,
                    message=message,
                    user=user,
                    level=log_level,
                    rule=log_rule,
                    more=more
                )
                if result:
                    ban_user(client, gid, uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    ask_for_help(client, "delete", gid, uid)
                    send_debug(
                        client=client,
                        chat=message.chat,
                        action=debug_action,
                        uid=uid,
                        mid=mid,
                        em=result
                    )
            else:
                if rule == "bio":
                    log_rule = lang("bio_examine")
                    debug_action = lang("bio_ban")
                elif rule == "name":
                    if more in {"contact", "content"}:
                        log_rule = lang("record_name")
                        debug_action = lang("name_ban")
                    else:
                        log_rule = lang("name_examine")
                        debug_action = lang("name_ban")
                elif rule == "record":
                    log_rule = lang("record_message")
                    debug_action = lang("record_ban")

                # Operation downgrade if possible
                if is_old_user(client, user, now, gid):
                    log_level = lang("auto_delete")
                    debug_action = lang("auto_delete")
                    more = lang("op_downgrade")
                    result = forward_evidence(
                        client=client,
                        message=message,
                        user=user,
                        level=log_level,
                        rule=log_rule,
                        more=more
                    )
                    if result:
                        delete_message(client, gid, mid)
                        declare_message(client, gid, mid)

                        if glovar.captcha_id in glovar.admin_ids[gid] and get_now() - now < glovar.time_captcha:
                            ask_help_captcha(client, gid, uid)
                        else:
                            ask_for_help(client, "delete", gid, uid, "global")

                        previous = add_detected_user(gid, uid, now)
                        not previous and update_score(client, uid)
                        send_debug(
                            client=client,
                            chat=message.chat,
                            action=debug_action,
                            uid=uid,
                            mid=mid,
                            em=result
                        )
                    result = False
                else:
                    if rule == "bio":
                        contacts = record_contacts_info(client, more)
                    elif rule == "name" and more not in {"contact", "content"}:
                        forward_name = get_forward_name(message, True)
                        full_name = get_full_name(user, True)
                        contacts = record_contacts_info(client, forward_name)
                        contacts = record_contacts_info(client, full_name) | contacts
                    else:
                        message_text = get_text(message, True)
                        contacts = record_contacts_info(client, message_text)
                        if message.new_chat_title:
                            contacts = contacts | record_contacts_info(client, message.new_chat_title)

                    result = forward_evidence(
                        client=client,
                        message=message,
                        user=user,
                        level=log_level,
                        rule=log_rule,
                        contacts=contacts,
                        more=more
                    )
                    if result:
                        add_bad_user(client, uid)
                        ban_user(client, gid, uid)
                        delete_message(client, gid, mid)
                        declare_message(client, gid, mid)
                        ask_for_help(client, "ban", gid, uid)
                        send_debug(
                            client=client,
                            chat=message.chat,
                            action=debug_action,
                            uid=uid,
                            mid=mid,
                            em=result
                        )

        return bool(result)
    except Exception as e:
        logger.warning(f"Terminate user error: {e}", exc_info=True)

    return False
