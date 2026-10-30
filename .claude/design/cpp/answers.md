# The owner's answers on the C++ design (2026-10-29 and 2026-10-30)

`design.md` is the full design (a copy of `design/cpp-header-only.md` from the design run) and `gate.md` the page the
owner saw. His answers, quoted, not widened:

- 2026-10-29, on the C++ binding's packaging: header-only with no ANTLR runtime, "but with as much auto codegen as
  possible to unify with typescript and python" (option A).
- 2026-10-30, on the C++ review page:
  - **Q1 A** (gate.md Q1; design.md 5.3 Q2): expected errors throw exceptions mirroring the error tree, as TypeScript
    and Python do.
  - **Q2** (gate.md Q2; design.md 5.3 Q1, handles), his note: "Are you asking about ref counting? Ok". Handles share
    ownership of the graph, reference counted, and never dangle (option A).
  - **Q3 A**: run each language's standard formatter on generated code, pinned to exact versions, instead of hand
    layout in emitters (for C++: clang-format).

Note the numbering: gate.md asks errors first (Q1) and handles second (Q2); design.md 5.3 has them the other way round.
The milestone 1 build plan is `frozen-m1.md` beside this file.
