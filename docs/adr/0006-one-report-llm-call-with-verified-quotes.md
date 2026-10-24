# ADR 0006 – One report-LLM call per conversation, quotes verified in code

**Status:** Accepted
**Date:** 2026-10-08

The session report gets mistakes, better phrasings, English→German, rescue phrases and retell scores from a single report-LLM call per conversation (Sonnet 5 via the gateway, JSON), while freeze times, listening aids and missed rescue chances are computed in code from `turns`. One call sees the whole conversation, so recurring errors can be grouped and retellings judged against the partner's real text; per-turn calls would cost ~N× and lose that context. The risk is the model "finding" errors the learner never made, which would break the promise of ADR 0005; so code keeps a finding only if its quoted fragment appears, as whole words, in that learner turn's stored transcript, and every drop is shown as a status line. Error categories are a fixed list (unknown → "Sonstiges") so "top 3" counts stay stable. If the call fails, the report still renders the numbers, `report_status='failed'`, and `stc report <id>` reruns it.
