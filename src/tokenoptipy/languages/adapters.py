from __future__ import annotations

from .generic import GenericLanguageAdapter


class PythonAdapter(GenericLanguageAdapter):
    language_id = "python"
    extensions = (".py",)
    markers = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")
    parser_name = "Python ast"
    experimental = False


class JavaScriptAdapter(GenericLanguageAdapter):
    language_id = "javascript"
    extensions: tuple[str, ...] = (".js", ".jsx", ".mjs", ".cjs")
    markers: tuple[str, ...] = ("package.json", "jsconfig.json")
    parser_name = "tree-sitter-javascript"
    experimental = False


class TypeScriptAdapter(JavaScriptAdapter):
    language_id = "typescript"
    extensions: tuple[str, ...] = (".ts", ".tsx")
    markers: tuple[str, ...] = ("tsconfig.json",)
    parser_name = "tree-sitter-typescript"


class PhpAdapter(GenericLanguageAdapter):
    language_id = "php"
    extensions = (".php",)
    markers = ("composer.json", "composer.lock", "artisan")
    import_patterns = (r"\b(?:require|require_once|include|include_once)\s*\(?\s*['\"](?P<value>[^'\"]+)", r"^\s*use\s+(?P<value>[\w\\]+)")


class JavaAdapter(GenericLanguageAdapter):
    language_id = "java"
    extensions = (".java",)
    markers = ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
    import_patterns = (r"^\s*import\s+(?P<value>[\w.]+)\s*;",)


class CAdapter(GenericLanguageAdapter):
    language_id = "c"
    extensions: tuple[str, ...] = (".c", ".h")
    markers: tuple[str, ...] = ("CMakeLists.txt", "Makefile", "meson.build")
    import_patterns = (r'^\s*#\s*include\s*"(?P<value>[^"]+)"',)


class CppAdapter(CAdapter):
    language_id = "cpp"
    extensions: tuple[str, ...] = (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx")
    markers: tuple[str, ...] = ("CMakeLists.txt", "Makefile", "meson.build", "conanfile.py", "conanfile.txt", "vcpkg.json")


class CSharpAdapter(GenericLanguageAdapter):
    language_id = "csharp"
    extensions = (".cs",)
    markers = ("global.json", "Directory.Build.props")
    import_patterns = (r"^\s*using\s+(?P<value>[\w.]+)\s*;",)

    def detect_project(self, root):  # type: ignore[no-untyped-def]
        return super().detect_project(root) or any(root.glob("*.sln")) or any(root.rglob("*.csproj"))


class GoAdapter(GenericLanguageAdapter):
    language_id = "go"
    extensions = (".go",)
    markers = ("go.mod", "go.work")
    import_patterns = (r'^\s*import\s+(?:\w+\s+)?"(?P<value>[^"]+)"', r'^\s*_\s+"embed"')


class RustAdapter(GenericLanguageAdapter):
    language_id = "rust"
    extensions = (".rs",)
    markers = ("Cargo.toml", "Cargo.lock")
    import_patterns = (r"^\s*(?:use|mod)\s+(?P<value>[\w:]+)", r'include_str!\s*\(\s*"(?P<value>[^"]+)"')
