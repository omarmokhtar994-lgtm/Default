# Phase AZ: redesign suggestions for every page

Written 2026-10-25 after looking at the real site on made-up "Associate NN" data (31 pages at 1440 px dark and light, and at 390 px;
screens in `audit/shots/`). Nothing here is applied to `webapp/`. Method: web-design-engineer (Preserve, with a bolder surface),
frontend-design, impeccable and taste (method only), Emil's animate and review rules, better-* review skills, web-interface-guidelines,
color-expert, site-architecture, design tokens, workflow-score-to-target (scores are judgements from the screens, 10 is best-in-class).

Design Read: operate screen for RTAs and planners, used all day, mostly on a desktop beside other tools, some phone use (associates, team
managers). Dials: variance 4, motion 3, density 7, assets 2, brand fidelity 8 (keep the mark, Archivo and Atkinson, state colours,
channel colours, routes, form field names, test selectors, CSRF and sign-in behaviour).

## 1. What is wrong today (found in the screens)

| # | Finding | Where | Severity |
|---|---|---|---|
| 1 | Sidebar items Shrinkage and Incidents show a grey square: `icons.css` has no icon rule for `/shrinkage` or `/incidents` (`.leftnav nav a[href^=...]`). A real defect, a two-line fix. | every page | high, easy |
| 2 | Top right reads "Light look Ocean look Settings Sign out" as four loose links; the two look links are a setting, not navigation, and look like sentence fragments. | every page | high |
| 3 | "‹ Back" and "Home" buttons on every page, above the title, push every title down and repeat what the sidebar and browser already do. | every page except Home | medium |
| 4 | Intro paragraphs of two to four lines under almost every title (Leave and swaps, People, Exports, Incidents, Notifications, Departments). They explain rules the screen should show. | most pages | medium |
| 5 | Home has "New schedule" three times (sidebar, top card, run card) and a 2,850 px page; the coverage grid is all violet (over-staffed), so the one thing that matters (gaps) is invisible. | Home | high |
| 6 | Week page is 9,257 px tall: "Extra hours available" is a 168-row table with no paging or collapse; the interval-target, hours-needed, rest-of-week and heat grid all stack with the same weight. | Week | high |
| 7 | RTA on a phone is 6,672 px: header wraps to four lines, the day controls and the lane list take the full length, no jump to "Now". | RTA phone | high |
| 8 | Incidents: the "Show" button is stretched tall beside the checkbox group; period chips, dates and selects are four different control styles. | Incidents | medium |
| 9 | Schedules: "Times in" defaults to UTC for an Egypt team (the rest of the site says Egypt time); the two-schedule comparison is good but its actions sit at the very bottom of a long table. | Schedules | medium |
| 10 | Sign in: a marketing headline (four lines, 72 px) beats the form; the form floats with no surface; the focus ring is the heaviest thing on the page. | Sign in | medium |
| 11 | Wallboard: good big tiles, but half the screen is empty and the page links back with small underlined text; nothing says how fresh the data is. | Wallboard | medium |
| 12 | Native dates show `mm/dd/yyyy` (browser locale) next to Egypt-format text everywhere else; amber, red and violet are used for status but also for buttons ("Approve" outline, "Delete" red) with little separation. | Incidents, Exports, forms | low |
| 13 | Run page: green "Approved" text is a bare word at top right; the card with the left teal rail is the "left-border accent card" the failure list warns about; the coverage heat repeats Home's all-violet problem. | Run | medium |
| 14 | Associate phone pages are clean but long: all seven days always open, three forms stacked, native `mm/dd/yyyy` fields. | My weeks, My day | low |

## 2. The system (shared by all three looks; prototype in `prototype/`)

- **Looks.** A Tide (light, sky gradient, soft cards), B Night watch (navy, hairline cards, dotted top glow), C Paper (cool grey, no card
  fill, hairline rules, 8 px radius). One token set; the look is a `data-look` attribute (kept in the existing `theme` cookie). Today's
  three looks (Graphite night, Day, Deep ocean) map to B, A and a deeper B; Paper (C) is new.
- **Colour means state.** Covered teal, short amber, gap red, over violet, always paired with a word or icon (never colour alone). Over-staffed
  becomes a quiet tint (not a solid block), so gaps and shortfalls are the only loud colours. Actions are ink (dark in A and C, light in B).
  Channels Phone blue, Chat magenta, Email green (brighter in B for contrast).
- **Type.** Archivo for headings and numerals (stretch 88%, weight 800), Atkinson Hyperlegible Next for text, tabular numbers everywhere.
  Subset the Archivo file (about 65 KB saved). One scale: 14, 16, 18, 24, clamp(32, 5vw, 50).
- **Layout.** One shell (max 78 rem), top bar = brand, five main links, Go to, person menu. Sidebar becomes the top bar on Home-level
  pages; deeper pages keep a slim sidebar only for admin areas. No Back/Home buttons: a breadcrumb line only on pages two levels deep.
- **Theme and account.** One "Look" control inside the person menu (Settings, Look: Tide, Night watch, Paper, Device), Sign out last.
- **Cards only where grouping matters** (failure-pattern "cardification"): tables, lists and forms sit on one surface; stat tiles are the only
  repeated cards.
- **Shadows.** Two strengths from beautiful-shadows as `--lift` and `--lift-big` (A, B); C has none.
- **Motion** (Emil's gate; prototype `proto.css`): none on the timeline, tabs, coverage cells or other frequent actions; floating note
  220 ms in, 160 ms out; request row closes with a 220 ms collapse; changed lane tints and fades 1.6 s; sign-in plays once; press 120 ms;
  look switch 200 ms cross-fade; reduced motion keeps 120 ms fades only. All opacity or transform, `--ease-out` cubic-bezier(.23,1,.32,1).
- **Floating "page out of date" note.** A fixed pill at the bottom (full width on phones) with Refresh and Hide; also carries
  "Approved, Undo" confirmations for 6 s; `role="status"`, Escape hides it.
- **Copy.** Sentence case; titles name the thing ("Leave and swaps"); help text becomes one short line under the title, longer rules go
  into an "About this page" disclosure.

## 3. Page by page

Scores: today / after (judgement from the screens; honest, not a promise).

### Account
- **Sign in** (today 5, after 8). Card on the look's background, mark above, 32 px "Sign in", one line of purpose, inline error
  under the password, button full width. Drop the weekly-schedule illustration from this page (it can live on a public "About" if you want
  it); keep the 40 ms stagger once per visit. Prototype: `p-signin`.
- **Change password** (5 to 8). Same card as sign in; strength rules as a live checklist ("10 characters, one number") instead of a paragraph.

### Everyone with RTA, planner, supervisor or admin access
- **Home** (4 to 8). "Good afternoon, Sara", the program line, three stat tiles (Right now, Waiting for you, Latest schedule) each with one
  link, a coverage strip that colours only gaps and shortfalls, then Runs as a list (name, small chip "In use" or "Not in use", five-step
  progress, percent). One "New schedule" button, which opens the new-run form as a panel instead of a 1,000 px form on the page. Prototype
  `p-home-a`.
- **New run form** (5 to 8). Three steps: what (build, upload ready, readiness check), the file (drop zone, program, start day, times in),
  how long (Quick, Deep, Overnight). Advanced options stay collapsed. The amber "This week already has schedules" warning becomes a one-line
  note with a link to Schedules.
- **RTA, real-time view** (6 to 8). Keep the density. Fix: a sticky strip with the program, day, "Now 14:36" and the stale-note; controls
  (Program, Day, Times in, Day starts at) collapse into one "View" popover on phones; "Jump to now" button; achievement bar keeps its marks
  but with word labels; the lane list uses the prototype's grid bars. The Undo banner becomes the floating note. Prototype `p-day-*`.
- **RTA tabs** (Timeline, Interval board, Adherence, Overview, Find a time, Booked sessions): turn into a proper tab row with counts only
  where something needs doing; same look everywhere.
- **Overview** (6 to 8). Same tile and strip pattern as Home; the page I could not read in full is the long one, so check every heading
  once in the build.
- **Wallboard** (7 to 9). Large tiles with the status as word plus colour, a visible "Updated 06:31:12" stamp, the lower area filled
  with the break and language lists in two columns, link back as a button. Best in B (navy). Prototype `p-wallboard-b`.
- **Handover note**, **Split view** (6 to 8). Print-friendly light page in every look; A4 stylesheet kept.
- **Week** (4 to 8). Page becomes a tabbed page: Summary (target, hours needed, rest of the week as small cards), Heat map, Overtime, Extra
  hours. "Extra hours available" gets a day filter and shows 24 rows with "Show all". Target slider keeps its form. Top of page = a one-line
  verdict ("100% covered, 0 h overtime needed").
- **Schedules** (6 to 8). Week tabs with counts, one comparison table (the best table on the site, kept), actions at the top of each
  column, "Delete…" opens a confirm sentence, "Times in" defaults to Cairo. Prototype `p-schedules-c`.
- **Run page** (5 to 8). Status chip instead of green text; the next action ("Plan breaks", "Open the schedule") as a primary row; coverage
  heat with only deviations coloured; "Edit details" stays a disclosure.
- **Run schedules / Schedule week / Plan breaks / Plan channels** (6 to 8). Same table skin, sticky first column and header, bar colours
  from the channel tokens, legends as chips.
- **Leave and swaps** (6 to 8). Tabs Waiting (count), Decided, Break changes, Coaching; each card shows the impact line ("Short by 0.8 from
  12:00 to 14:00") as an amber strip, the decision buttons stay beside it, a decided row collapses with Undo. Prototype `p-requests-a`.
- **Coaching requests / Break changes**: same card, one verb per button ("Approve", "Decline", never "Refuse").
- **Incidents and shrinkage** (6 to 8). Period chips become one segmented control; From, To, Program, Measure in one row; absenteeism
  counts in a "What counts" popover; one "Show" button aligned to the row. KPI tiles get a sparkline and an arrow with words ("up 0.4 points").
- **Shrinkage page / coach** (6 to 8). Same filter row; coach steps as a numbered list only where it is a real sequence.
- **Analysis (program page)** (6 to 8). The trend lines keep their colours; add direct labels instead of a legend; one chart per row.
- **Programs** (6 to 8). Program cards become a compact table (program, LOBs, latest week, status).
- **Exports** (6 to 8). Period chips plus dates in one row; Include list in two columns with the long hints on a second line in dim text;
  "In this period" becomes a sticky side summary with one primary "Download".
- **Team** (6 to 8). Table, plus a bar for approved versus other; empty area filled by a short "how runs are counted" note.
- **People (admin users)** and **Add many from a file** (6 to 8). "Add a person" collapses to a drawer; the people list is the page, with search,
  role filter, on/off switch and a row menu; bulk upload as a three-step panel.
- **Roles** (6 to 8). Matrix with sticky role column; every cell a labelled toggle.
- **Departments and people, Associate channels, LOBs and defaults, Program setup** (6 to 8). Two-column form pages with the list on the left
  and "Add" as a right panel; paste-a-list box with a real example and a live count of lines.
- **Notifications** (6 to 8). LOB table on top, detail below; Posting as a three-choice segmented control (On, Preview only, Off) with a
  status dot; test message result shown in the floating note.
- **Command bar (Ctrl K)**: restyle as a centred panel with the same tokens; no motion (opened many times a day).

### Associates and team managers (phone first)
- **My day / My weeks** (6 to 8). Today card on top with the shift, next break and a "Request a change" button; the week as a list with
  today expanded and other days collapsed; request forms in bottom sheets; dates use a plain text field with a picker button and an Egypt
  format hint; request status chips ("Waiting for your TM").
- **Team manager approvals**: same as Leave and swaps, one column.

## 4. Order of work (after you pick)

1. Tokens + shell + theme control + floating note + icon fix (all pages change, no layout moves). Check: suites, browser tests, 31 pages x
   2 widths, contrast script, screens.
2. Home, RTA, Wallboard, Requests, Schedules (the five used daily).
3. Week, Run, Incidents, Exports, setup and admin pages.
4. Associate phone pages and Sign in.
Each step ends with the full suites, browser tests, page review and a patch, as in earlier phases. Engine untouched.

## 5. Decisions for you

1. Which look is the default: A, B or C (all three can ship; C is new).
2. Drop the sign-in schedule illustration and big headline? (suggested yes)
3. Remove "Back" and "Home" buttons in favour of breadcrumbs? (suggested yes)
4. Move the Week page's long tables behind tabs and "Show all"? (suggested yes)
5. Fix the two missing sidebar icons now, as a small separate fix? (suggested yes; a defect, not a redesign)
