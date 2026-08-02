# Language support

TokenOptiPy 0.5 performs local static analysis only. Python and Node adapters retain their AST and Tree-sitter implementations. PHP, Java, C, C++, C#, Go, and Rust are experimental structural adapters: they recognize native multiline/raw strings, local imports, prompt identifiers, dynamic placeholders, and model calls only when SDK/import, argument, endpoint, or payload evidence is present.

Ruby, Kotlin, Swift, Dart, Scala, F#, and Visual Basic .NET are extension targets for future adapters; they are not claimed as analyzed in 0.5.0. Reflection, complex macros, generated code, and runtime-built flows may be invisible.

Run `tokenoptipy languages [PATH]` or add `--json` to inspect availability and file counts. `auto` detects projects; `all` selects all registered adapters; repeated `--language` flags form an explicit selection.
