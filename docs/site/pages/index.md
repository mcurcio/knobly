# Quickstart

villanelle is a small configuration language with one grammar and three bindings: TypeScript, Python and C++.
Every sample on this site has a tab per language; pick one and every page follows it.

<!-- Skeleton page (.claude/design/cpp/frozen-docs.md): the "pages" slice writes the Quickstart here. -->

## Read a value

A file, `hello.conf`:

```conf
--8<-- "examples/fixtures/hello/hello.conf"
```

The program loads it, renders it and reads the one string:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/hello.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/hello.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/hello.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/hello.txt"
```
