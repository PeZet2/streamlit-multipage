from dataclasses import dataclass, field
from typing import List, Callable, ClassVar, Any, Dict, NamedTuple
from collections import defaultdict
from pathlib import Path
import copy

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

try:
    import joblib as pickling
except ImportError:
    import pickle as pickling


@dataclass
class StateManager:
    path: Path = Path(__file__).resolve().parent
    cache: Path = path / "cache"
    cache_filename: str = "data.pkl"

    @property
    def cache_file(self) -> Path:
        return self.cache / self.cache_filename

    def change_page(self, page: int) -> None:
        self.save({"current_page": page}, ["global"])

    def read_current_page(self) -> int:        
        data = self.load()["global"]
        if "current_page" in data:
            return int(data["current_page"])
        return 0

    @st.cache(suppress_st_warning=True)
    def _initialize(self, initial_page: int) -> None:
        self.change_page(initial_page)

    def save(self, variables: Dict[str, Any], namespaces: List[str] = None) -> None:
        if not variables:
            return
        
        if namespaces is None:
            namespaces = ["global"]

        data = self.load()

        new_data = {namespace: variables for namespace in namespaces}

        for namespace, variables in new_data.items():
            if namespace in data:
                data[namespace].update(variables)
                continue

            data[namespace] = variables

        self._save(data)

    def _save(self, data: Dict[str, Any]) -> None:
        self.cache.mkdir(parents=True, exist_ok=True)
        pickling.dump(data, open(self.cache_file, 'wb'))

    def load(self) -> Dict[str, Any]:
        if not self.cache_file.exists():
            return defaultdict(dict)
        
        data = self._load()
        
        if "global" in data:
            data.update(data["global"])

        return data

    def _load(self) -> Dict[str, Any]:
        try:
            return pickling.load(open(self.cache_file, 'rb'))
        except EOFError:
            return defaultdict(dict)

    def is_logged_in(self) -> bool:
        return "username" in self.load().get('session', '') and "token" in self.load().get('session', '')

    def clear_cache(self, *, 
                    variables: Dict[str, Any] = None, 
                    namespaces: List[str] = None, 
                    all_variables: bool = False) -> None:
                
        data = self.load()
        temp_data = copy.deepcopy(data)

        # Delete all variables from all namespaces
        if all_variables:
            for namespace in temp_data.keys():
                try:
                    del data[namespace]
                except KeyError:
                    ...
        
        # Delete all variables for given namespace list
        elif namespaces and not variables:
            for namespace in namespaces:
                try:
                    del data[namespace]
                except KeyError:
                    ...
        
        # Delete given variables from all namespaces
        elif variables:
            for namespace in temp_data.keys():
                for variable in variables:
                    try:
                        del data[namespace][variable]
                    except KeyError:
                        ...
                            
        self._save(data)

        # Delete cache file if all data are to be erased 
        if all_variables:
            if self.cache_filename:
                self.cache_file.unlink(missing_ok=True)


state = StateManager()


class App(NamedTuple):
    name: str
    func: Callable


@dataclass
class MultiPage:
    st = None
    __apps: List[App] = field(default_factory=list)
    __initial_page: App = None
    __state_manager: ClassVar[StateManager] = state
    __header: App = None
    __footer: App = None
    __navbar_extra: App = None
    start_button: str = "Let's go!"
    navbar_name: str = "Navigation"
    next_page_button: str = "Next Page"
    previous_page_button: str = "Previous Page"
    reset_button: str = "Reset Cache"
    navbar_style = "Button"
    hide_menu: bool = False
    hide_navigation: bool = False

    @property
    def apps(self) -> List[App]:
        return self.__apps

    @property
    def initial_page(self) -> App:
        return self.__initial_page

    @initial_page.setter
    def initial_page(self, value: Callable) -> None:
        self.__initial_page = App("__INITIALPAGE__", value)      

    @property
    def header(self) -> App:
        return self.__header

    @header.setter
    def header(self, value: Callable) -> None:
        self.__header = App("Header", value)

    @property
    def footer(self) -> App:
        return self.__footer

    @footer.setter
    def footer(self, value: Callable) -> None:
        self.__footer = App("Footer", value)

    @property
    def navbar_extra(self) -> App:
        return self.__navbar_extra

    @navbar_extra.setter
    def navbar_extra(self, value: Callable) -> None:
        self.__navbar_extra = App("Navbar_extra", value)

    def add_app(self, name: str, func: Callable, initial_page: bool = False) -> None:
        # only first occurrence
        if initial_page and not self.initial_page:
            self.initial_page = func
            return

        new_app = App(name, func)
        self.apps.append(new_app)

    def _render_next_previous(self, sidebar):
        left_column, middle_column, right_column = sidebar.columns(3)
        page = self.__state_manager.read_current_page()

        if middle_column.button(self.reset_button):
            self.change_page(-1)

        if left_column.button(self.previous_page_button):
            page = max(0, page - 1)
            self.change_page(page)

        if right_column.button(self.next_page_button):
            page = min(len(self.apps) - 1, page + 1)
            self.change_page(page)

    def _render_navbar(self, sidebar) -> None:

        if not self.hide_navigation:
            self._render_next_previous(sidebar)

        sidebar.markdown(
            f"""<h1 style="text-align:center;">{self.navbar_name}</h1>""",
            unsafe_allow_html=True,
        )
        sidebar.text("\n")

        possible_styles = ["VerticalButton", "HorizontalButton", "SelectBox"]

        if self.navbar_style not in possible_styles:
            sidebar.warning("Invalid Navbar Style - Using Button")
            self.navbar_style = "VerticalButton"

        if "Button" in self.navbar_style:
            if self.navbar_style == "HorizontalButton":
                columns = sidebar.columns(len(self.apps))
                for index, (column, app) in enumerate(zip(columns, self.apps)):
                    if column.button(app.name):
                        self.change_page(index)

            elif self.navbar_style == "VerticalButton":
                for index, app in enumerate(self.apps):
                    if sidebar.button(app.name, use_container_width=True):
                        self.change_page(index)

        if self.navbar_style == "SelectBox":
            app_names = [app.name for app in self.apps]
            app_name = sidebar.selectbox("", app_names)
            next_page = app_names.index(app_name)
            self.change_page(next_page)

        sidebar.write("---")

        if self.navbar_extra:
            self.navbar_extra.func(self, sidebar)

    def _run(self) -> None:

        if not self.is_logged_in() or self.hide_menu:
            hide_menu = """
                <style>
                #MainMenu {display: none;}
                footer {visibility: hidden;}
                </style>
            """
            st.markdown(hide_menu, unsafe_allow_html=True)

        # If not logged in - load initial page
        if not self.is_logged_in():
            self.initial_page.func(self)
        
        # If logged in - load hole page    
        else:
            if self.header:
                self.header.func(self)
    
            self._render_navbar(st.sidebar)

            if not self.is_logged_in():
                self.initial_page.func(self)
                return

            page = self.__state_manager.read_current_page()
            if page >= len(self.apps):
                page = 0
            
            app = self.apps[page]
            app.func(self)
    
            if self.footer:
                self.footer.func(self)

    def run(self, avoid_collisions: bool = True) -> None:
        if avoid_collisions:
            session_id = add_script_run_ctx().streamlit_script_run_ctx.session_id
            cache_filename = f"{session_id}.pkl"
            if cache_filename != self.__state_manager.cache_filename:
                self.__state_manager.cache_filename = cache_filename
            self._run()
    
    def clear_cache(self, *, 
                    variables: Dict[str, Any] = None,
                    namespaces: List[str] = None,
                    all_variables: bool = False) -> None:
        self.__state_manager.clear_cache(variables=variables, namespaces=namespaces, all_variables=all_variables)

    def save(self, variables: Dict[str, Any], namespaces: List[str] = None) -> None:
        self.__state_manager.save(variables, namespaces)

    def load(self) -> None:
        self.__state_manager.load()

    def change_page(self, page: int) -> None:
        self.__state_manager.change_page(page)

    def is_logged_in(self) -> bool:
        return self.__state_manager.is_logged_in()        

    def login(self, username: str, token: str) -> None:
        self.save(variables={"username": username, "token": token}, namespaces=["session"])
        self.change_page(0)
        st.rerun()

    def logout(self) -> None:
        self.clear_cache(all_variables=True)
        self.change_page(-1)
        st.rerun()
