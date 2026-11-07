# ZYNOVA CONNECT — GROUPS & COMMUNITIES ENGINE
**Group Roles, Moderation, Permissions, and Community Hierarchies**  

---

## 1. Group Chat Governance

- **Creator & Admins**: The creator is granted initial admin status (`admin_ids`). Admins can add or remove members, update group details (name, picture, description), and promote other members.
- **Invite Codes**: Groups generate secure base64 token invite codes (`invite_code`) enabling link-based onboarding.
- **Member Ejection**: When a user leaves or is removed by an admin, their participant meta and unread counts are atomically removed via `$pull`.

---

## 2. Communities Architecture

Communities allow organizations, neighborhoods, or topic-based groups to organize related subgroups under one umbrella:
- **Announcement Channel**: Every community automatically initializes an official Announcement group (`announcement_group_id`) where only community admins have write permissions.
- **Subgroup Binding**: Multiple group chats bind to `community_id`.
- **Discovery**: Users can browse community-associated groups according to permissions.
