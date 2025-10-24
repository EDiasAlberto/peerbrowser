from bs4 import BeautifulSoup
from bs4.element import Tag
from dataclasses import dataclass

REMOTE_FILE_PROTOCOLS = ("https://", "http://")
CSS_IMPORT_SYNTAX = "@import"



@dataclass
class SiteDependencies:
    
    def html_is_inline_or_remote_ref(self, tag: Tag, ref_attr: str) -> bool:
        return (tag.get(ref_attr) is None) or tag.get(ref_attr).lower().startswith(REMOTE_FILE_PROTOCOLS)
    
    def css_is_import(self, line: str) -> bool:
        return line.lower().startswith(CSS_IMPORT_SYNTAX)

    def css_is_linked_statement(self, line: str) -> bool:
        return "url(" in line

    def css_get_import_path(self, line: str) -> str:
        path_and_trailing_chars = line.split("url(")[-1]
        trimmed_path = path_and_trailing_chars.split(")")[0]
        return trimmed_path.strip("'").strip('"')

    def get_all_css_dependencies(self, filename: str) -> list[str]:
        link_or_import_statements = []
        with open(filename) as fp:
            line = fp.readline()
            while line != "":
                if self.css_is_import(line) or self.css_is_linked_statement(line):
                    import_path = self.css_get_import_path(line)
                    link_or_import_statements.append(import_path)
                line = fp.readline()
        return link_or_import_statements

    def get_all_html_dependencies(self, filename: str) -> list[str]:
        with open(filename) as fp:
            soup = BeautifulSoup(fp, "html.parser")
        code_dependencies = soup.find_all(["link", "script"])
        filtered_dependencies = []
        for tag in code_dependencies: 
            if tag.name == "link":
                if not self.html_is_inline_or_remote_ref(tag, "href"):
                    filtered_dependencies.append(tag["href"])
            elif tag.name == "script":
                if not self.html_is_inline_or_remote_ref(tag, "src"):
                    filtered_dependencies.append(tag["src"])
        return filtered_dependencies
    
    def get_all_js_dependencies(self, filename: str) -> list[str]:
        # TODO: implement js parsing to find imports
        print(f"Checking {filename} for import statements")


if __name__=="__main__":
    parser = SiteDependencies()
    print(parser.get_all_html_dependencies("test-site/index.html"))
    print(parser.get_all_css_dependencies("test-site/css/main.css"))
