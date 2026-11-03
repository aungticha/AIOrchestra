# Editorial Video Workflow

Producer -> Content Researcher / Story Producer -> Script / Storyboard -> User Accept 1 -> Video Editor with optional Graphic/Audio in parallel -> Editor assembly -> QA/fix loop -> User Accept 2 -> final export.

- Producer collects the brief and uses supplied references; if missing, searches for a small relevant shortlist before Accept 1. Missing access/tools must be reported, never simulated.
- Content Researcher / Story Producer researches factual sources, selects essential information without losing context, and delivers a scene-level Story Plan with claim/source IDs. Disable this planning node before starting when a verified plan is already supplied.
- Writer turns the Story Plan into sourced dialogue per scene and inspects the visual reference and creates a timestamped original storyboard with camera/editing/effect/audio evidence and CapCut guidance.
- Accept 1 approves the selected inspected reference, content sources, Story Plan, script, storyboard and production scope. Starting a job is not acceptance.
- Editor, Graphic and Audio own separate outputs. Parallel agents do not write the same CapCut draft. Editor integrates their assets at the assembly barrier before QA.
- QA inspects the actual preview, factual claims, source traceability and context. Editing findings return to production; material factual/story corrections return to planning and renewed Accept 1. Corrections are checked again, up to the configured correction limit.
- Accept 2 approves the reviewed preview before final export. Export requires an available real CapCut capability; otherwise the job stays blocked for manual handoff.
- Graphs and approvals are saved per run. Changes to the team's template affect future runs only. No automatic Git commit/push belongs to a video workflow.

The Dashboard/server executes WORKFLOW.json; this Markdown records the human-readable rules. CLI authentication and actual video/search/CapCut tools remain prerequisites.

## Planning-only scope
Choose this explicitly for script/storyboard/filming plans without producing media: Producer -> Researcher -> Writer -> User Accept 1 -> completed. Original planning needs no style-reference clip or existing footage; verify factual sources. Reference-based planning still requires actual visual inspection. Full production keeps both original approval gates.

Each agent sets passed=true when its own deliverables are complete. Producer does not block because Researcher/Writer work is pending, and Researcher does not wait for a final script. blocked=true means a real prerequisite prevents the current role from completing its own work. Writer supplies a real script/storyboard planning artifact; the controller verifies acceptance readiness after Writer. Never convert a blocked result to success automatically.
