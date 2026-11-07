# PHASE 28 — UNIFIED APPLICATION NAVIGATION & ROUTING SPECIFICATION

## 1. Overview
The Zynova navigation architecture delivers a seamless experience across desktop, tablet, and mobile form factors with zero duplication between modules.

---

## 2. Primary Destinations & Hierarchies

### 2.1 Primary Destinations (Top-Level)
1. **Home** (`#/home`): Core hub presenting personalized highlights from Social, Connect unread summaries, and recommended Videos.
2. **Social** (`#/social`): Posts, stories, reels, and user profiles.
3. **Connect** (`#/chat`): Direct messages, group chats, communities, and status stories.
4. **Video** (`#/video`): Long-form videos, Shorts feed, creator channels, and playlists.
5. **Search** (`#/search`): Global multi-category discovery.
6. **Notifications** (`#/notifications`): Unified notification center.
7. **Profile / Settings** (`#/settings`): Account security, preferences, and privacy controls.

### 2.2 Secondary Destinations (Accessible via Command Palette & Sidebars)
- **AI Assistant** (`#/ai-assistant`)
- **Shopping (Zaviro)** (`#/shopping`)
- **Food & Dining** (`#/food`)
- **Payments / Wallet** (`#/payments`)
- **Customization Studio** (`#/customization`)

---

## 3. Responsive Layout Patterns

### 3.1 Desktop (`md:` breakpoint and above)
- **Collapsible Sidebar**: Left-aligned navigation with full labels or icon-only compact mode (`w-64` vs `w-[68px]`).
- **TopBar**: Quick profile switcher, notification badge, and command palette trigger (`Ctrl+K`).
- **Main Viewport**: Dynamically rendered view with smooth React Suspense fallback.

### 3.2 Mobile & Android
- **Bottom Navigation Bar**: 5 essential touch targets: Home, Social, Connect, Video, and Search.
- **Drawer Menu**: Slide-out panel for accessing secondary destinations and appearance settings.
- **Hardware Android Back Button**: Integrated with window `popstate` and `Escape` handlers to close active drawers and navigate back safely without exiting the application prematurely.
