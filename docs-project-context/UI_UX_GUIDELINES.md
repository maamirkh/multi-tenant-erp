# UI_UX_GUIDELINES.md

# DevSphere ERP

## Official UI / UX Guidelines

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official User Interface (UI) and User Experience (UX) standards for DevSphere ERP.

Every screen, component, page and future module must follow these guidelines.

This document is the single source of truth for frontend design.

---

# Design Philosophy

DevSphere ERP follows these principles:

* Clean
* Modern
* Professional
* Fast
* Accessible
* Consistent
* Mobile Friendly
* Enterprise Ready

The interface should reduce cognitive load and maximize productivity.

---

# Design Language

Preferred style

* Minimal
* Flat Design
* Soft Shadows
* Rounded Corners
* Clear Hierarchy
* Large Click Targets

Avoid unnecessary visual complexity.

---

# Target Users

The UI is designed for:

* Business Owners
* Managers
* Accountants
* Sales Teams
* Warehouse Staff
* HR Staff
* Cashiers
* Super Admins

Most users are not technical.

The interface must be easy to understand.

---

# Design System

Every component should use reusable design tokens.

Never hardcode colors or spacing.

---

# Color Palette

## Primary

```text id="1"
Blue
#2563EB
```

Used for

* Primary Buttons
* Links
* Active Navigation
* Selected Items

---

## Success

```text id="2"
Green
#16A34A
```

Used for

* Success Messages
* Completed Status
* Payments Received

---

## Warning

```text id="3"
Orange
#F59E0B
```

Used for

* Pending
* Draft
* Attention Required

---

## Danger

```text id="4"
Red
#DC2626
```

Used for

* Delete
* Errors
* Critical Alerts

---

## Info

```text id="5"
Sky Blue
#0EA5E9
```

Used for

* Notifications
* Information
* Tips

---

## Neutral

```text id="6"
Gray Scale

50
100
200
300
400
500
600
700
800
900
```

Used throughout the application.

---

# Typography

Primary Font

Inter

Fallback

```text id="7"
Arial

sans-serif
```

---

# Font Sizes

```text id="8"
Page Title

32

Section

24

Card Title

20

Body

16

Small Text

14

Caption

12
```

Never use arbitrary font sizes.

---

# Font Weight

```text id="9"
Normal

400

Medium

500

Semi Bold

600

Bold

700
```

---

# Border Radius

Standard

```text id="10"
8px
```

Cards

```text id="11"
12px
```

Dialogs

```text id="12"
16px
```

---

# Shadows

Soft elevation only.

Avoid heavy shadows.

Cards

```text id="13"
Small Shadow
```

Dialogs

```text id="14"
Medium Shadow
```

Dropdowns

```text id="15"
Medium Shadow
```

---

# Spacing System

Use an 8px grid.

```text id="16"
4

8

16

24

32

40

48

64
```

Never use random spacing.

---

# Layout Width

Desktop

Maximum

```text id="17"
1440px
```

Content should remain centered.

---

# Sidebar

Width

```text id="18"
280px
```

Collapsed

```text id="19"
80px
```

---

# Top Navigation

Height

```text id="20"
64px
```

Contains

* Search
* Notifications
* Company Switcher
* User Menu

---

# Dashboard Cards

Each dashboard card includes

* Icon
* Title
* Value
* Trend
* Small Description

Cards should remain consistent.

---

# Buttons

Primary

Filled Blue

Secondary

Outline

Danger

Filled Red

Success

Filled Green

Ghost

Transparent

Icon Button

Square

---

# Button Sizes

Small

Medium

Large

Never invent new sizes.

---

# Forms

Every form includes

* Label
* Placeholder
* Helper Text
* Validation
* Error Message

Required fields must display an asterisk.

---

# Form Validation

Validation occurs

* On Blur
* On Submit

Never validate every keystroke unless necessary.

---

# Input Controls

Supported

* Text
* Number
* Currency
* Date
* Time
* Select
* Multi Select
* Checkbox
* Radio
* Toggle
* Textarea

Maintain consistent styling.

---

# Tables

Enterprise tables support

* Pagination
* Search
* Filters
* Sorting
* Export
* Column Visibility
* Bulk Actions

---

# Table Actions

Prefer icons with tooltips.

Examples

* View
* Edit
* Delete
* Print
* Duplicate

---

# Status Badges

Examples

Green

Active

Red

Inactive

Orange

Pending

Gray

Draft

Blue

Completed

Use consistent colors across all modules.

---

# Modals

Use dialogs only when necessary.

Every dialog includes

* Title
* Description
* Primary Action
* Secondary Action

Danger dialogs require confirmation.

---

# Notifications

Success

Green

Warning

Orange

Error

Red

Info

Blue

Notifications disappear automatically except critical errors.

---

# Loading States

Never leave blank pages.

Use

* Skeleton Loaders
* Progress Bars
* Spinner

---

# Empty States

Every empty screen should explain

* Why it is empty
* What to do next

Example

"No products found."

---

# Search UX

Search should support

* Instant Search
* Keyboard Navigation
* Clear Button

Large datasets should use server-side search.

---

# Filters

Filters should be collapsible.

Allow

* Reset
* Apply
* Saved Filters (future)

---

# Breadcrumbs

Display breadcrumbs on every major page.

Example

```text id="21"
Dashboard

>

Inventory

>

Products

>

Edit
```

---

# Navigation

Sidebar groups

Dashboard

Company

Inventory

Purchases

Sales

Accounting

HR

CRM

Reports

Settings

Administration

Navigation should remain identical across tenants.

---

# Icons

Preferred

Lucide Icons

Use one consistent icon library.

---

# Charts

Preferred

Recharts

Supported

* Line
* Bar
* Pie
* Area
* Donut

Charts should remain simple.

---

# Responsive Design

Breakpoints

```text id="22"
Mobile

640

Tablet

768

Laptop

1024

Desktop

1280

Large

1536
```

---

# Mobile Rules

Sidebar becomes drawer.

Tables become responsive.

Buttons become full width where appropriate.

---

# Dark Mode

Supported.

Requirements

* Accessible contrast
* Same spacing
* Same layout
* Same functionality

Never rely on color alone.

---

# Accessibility

Follow WCAG 2.1 AA.

Requirements

* Keyboard Navigation
* Focus Indicators
* Screen Reader Support
* Color Contrast
* Labels
* ARIA where required

Accessibility is mandatory.

---

# Error Pages

Provide dedicated pages for

* 401
* 403
* 404
* 500

Each page should guide the user.

---

# Confirmation Dialogs

Required for

* Delete
* Cancel Invoice
* Reverse Transaction
* Reset Password
* Archive Records

---

# ERP UX Principles

Always prioritize

* Speed
* Accuracy
* Visibility
* Minimal Clicks

Users perform repetitive tasks daily.

The interface should optimize productivity.

---

# AI Generated Screens

AI-generated frontend code must:

* Follow this design system
* Reuse components
* Avoid inline styles
* Use design tokens
* Respect spacing
* Maintain consistency

---

# Component Library

Reusable components include

* Button
* Input
* Select
* Modal
* Table
* Badge
* Card
* Alert
* Toast
* Tabs
* Pagination
* Breadcrumb
* Sidebar
* Navbar
* Loader
* Empty State

No duplicate components should exist.

---

# Future Expansion

The design system should support:

* White Labeling
* Theme Customization
* RTL Languages
* Localization
* Mobile Apps

Without requiring major redesign.

---

# Single Source of Truth

This document defines the official UI and UX standards for DevSphere ERP.

Every page, component and future feature must comply with these guidelines.
