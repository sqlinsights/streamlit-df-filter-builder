import streamlit as st
import pandas as pd
from vega_datasets import data as vd
import uuid
from black import format_str, FileMode
from io import StringIO

st.set_page_config(layout="wide")


# GLOBAL VARIABLES
if "expression_groups" not in st.session_state:
    st.session_state["expression_groups"] = []

if "expressions" not in st.session_state:
    st.session_state["expressions"] = {}
if "workflow_mode" not in st.session_state:
    st.session_state["workflow_mode"] = None

expression_mapping = {
    "CONTAINS": "df['{0}'].str.contains('{1}')",
    "IN": "df['{0}'].isin({1})",
    "NOT IN": "~df['{0}'].isin({1})",
    "EQUALS": "df['{0}']=='{1}'",
    "NOT EQUALS": "df['{0}']!=('{1}')",
    "GREATER THAN": "df['{0}']>{1}",
    "GREATER/EQUAL THAN": "df['{0}']>={1}",
    "LOWER THAN": "df['{0}']<{1}",
    "LOWER/EQUAL THAN": "df['{0}']<={1}",
}
options_mapping = {"AND": "&", "OR": "|"}
available_dataframes = {
    "Airports": vd.airports,
    "Seattle Weather": vd.seattle_weather,
    "Stocks": vd.stocks,
    "Cars": vd.cars,
}
groups = []
MAX_EXPRESSION_COUNT = 2


def get_data(dataset):
    fn = available_dataframes.get(dataset)
    return fn()


def build_filters(grouped_expressions) -> str:
    flattened_expressions = "".join(
        [
            f"{options_mapping.get(i.get('binder'),'') } {i.get('expressions')}"
            for i in groups
        ]
    )
    return f"""df.loc[{flattened_expressions}]"""


# CLASS DEFINITIONS


class BlackFormat:
    def __init__(self, raw_string: str) -> None:
        self.raw_string = raw_string

    def __repr__(self) -> str:
        try:
            formatted_str = format_str(
                self.raw_string,
                mode=FileMode(
                    line_length=50,
                ),
            )
        except:
            formatted_str = "⚠️ Errors found in expressions"
        finally:
            return formatted_str


class Callbacks:

    @staticmethod
    def reset_ss():
        st.session_state.clear()

    @staticmethod
    def add_group():
        st.session_state["expression_groups"].append(str(uuid.uuid4()))

    @staticmethod
    def add_expression(group: str):
        if st.session_state["expressions"].get(group) == None:
            st.session_state["expressions"][group] = [str(uuid.uuid4())]
        else:
            st.session_state["expressions"][group].append(str(uuid.uuid4()))

    @staticmethod
    def remove_group(group: str):
        st.session_state["expression_groups"].remove(group)

    @staticmethod
    def remove_expression(group: str, expression: str):
        st.session_state["expressions"][group].remove(expression)


class Group:
    @classmethod
    def render_group(cls, index: int, group_id: str):
        if index > 0:
            binder, delete = st.columns((2, 0.5))
            group_binder = binder.radio(
                "",
                label_visibility="collapsed",
                options=options_mapping,
                key=f"binder{group_id}",
                horizontal=True,
            )
            delete.button(
                "🗑️",
                key=f"remove{group_id}",
                on_click=Callbacks.remove_group,
                args=[group_id],
                use_container_width=True,
            )
        else:
            group_binder = "root"
        with st.expander(label=f"Filter Group: {str(index + 1)}", expanded=True):
            expression_data = []
            st.button(
                "Add Expression",
                on_click=Callbacks.add_expression,
                args=[group_id],
                key=f"btn_{group_id}",
                help="test",
                disabled=len(st.session_state["expressions"].get(group_id, []))
                == MAX_EXPRESSION_COUNT,
            )

            for expression_idx, expression in enumerate(
                st.session_state["expressions"].get(group_id, [])
            ):
                expression = Expression.render_expression(
                    index=expression_idx,
                    expression_id=expression,
                    group_id=group_id,
                )
                if len(expression) > 0:
                    expression_data.extend(expression)
            if len(expression_data) > 0:
                results = dict(
                    group=group_id,
                    binder=group_binder,
                    expressions=f"""({"".join(expression_data)})""",
                )
                st.caption(
                    "Filter Code",
                    help=f"""``` 
                        {BlackFormat(raw_string=results.get("expressions"))}""",
                )
            else:
                results = None

        return results


class Expression:
    @classmethod
    def render_expression(cls, index: int, expression_id: str, group_id: str):
        binder = st.container()
        field, operator = st.columns(2)
        values, delete = st.columns((3, 0.5))
        if index > 0:
            exp_binder = binder.radio(
                "",
                label_visibility="collapsed",
                options=options_mapping,
                key=f"binder{expression_id}",
                horizontal=True,
            )
        else:
            exp_binder = "root"
        field_name = field.selectbox(
            "",
            label_visibility="collapsed",
            options=df.columns,
            key=f"field_name{expression_id}",
        )
        operator_type = operator.selectbox(
            "Operator",
            options=expression_mapping,
            label_visibility="collapsed",
            key=f"operator{expression_id}",
        )

        if operator_type in ["IN", "NOT IN"]:
            exp_value = values.multiselect(
                "",
                label_visibility="collapsed",
                key=f"values_in{expression_id}",
                options=df[field_name].sort_values().unique(),
            )

        if operator_type in [
            "GREATER THAN",
            "LOWER THAN",
            "GREATER/EQUAL THAN",
            "LOWER/EQUAL THAN",
        ]:
            if df[field_name].dtype in ["float", "float64", "int64"]:
                exp_value = values.number_input(
                    "",
                    placeholder="Enter Value",
                    label_visibility="collapsed",
                    key=f"values_nm{expression_id}",
                )
            elif df[field_name].dtype in ["datetime64[ns]"]:
                exp_value = f"""'{values.date_input(
                    "",
                    label_visibility="collapsed",
                    value=df[field_name].max(),
                    min_value=df[field_name].min(), 
                    max_value=df[field_name].max(),
                    key=f"values_dt{expression_id}",
                )}'"""
            else:
                values.warning("Invalid expression for Data Type")
                exp_value = None

        if operator_type in ["CONTAINS", "EQUALS", "NOT EQUALS"]:
            exp_value = values.text_input(
                "",
                placeholder="Enter Value",
                label_visibility="collapsed",
                key=f"values_ms{expression_id}",
            )

        delete.button(
            "🗑️",
            key=f"remove{expression_id}",
            on_click=Callbacks.remove_expression,
            args=[group_id, expression_id],
            use_container_width=True,
        )
        if exp_value:
            results = (
                f"""{options_mapping.get(exp_binder, '')}({expression_mapping.get(operator_type).format(
                    field_name, exp_value
                )})""",
            )
        else:
            values.warning("Value cannot be blank")
            results = []

        return results


# -----------------------------------------------------------------------------------
# PROGRAM EXECUTION STARTS HERE


st.title("Filtering a Dataframe")
df_container = st.container()


groups = []
sidebar = st.sidebar
with sidebar:
    with st.expander("Mode"):
        workflows = {1: "Paste my Data", 2: "Use Sample Data"}
        mode = st.radio(
            "",
            label_visibility="collapsed",
            options=[1, 2],
            horizontal=True,
            format_func=lambda x: workflows.get(x),
            on_change=Callbacks.reset_ss,
        )

    if mode == 1:
        input_data_exp = df_container.expander("Data Input", expanded=True)
        pasted_data = input_data_exp.text_area(
            "Paste your CSV Data Here", label_visibility="collapsed", height=200
        )
        if pasted_data:
            try:
                df = pd.read_csv(StringIO(pasted_data))
            except:
                df_container.error("Invalid CSV")
                df = pd.DataFrame()
        else:
            df_container.info("Paste your CSV content to proceed.")
            df = pd.DataFrame()
    if mode == 2:
        dataset = df_container.selectbox(
            "Available Datasets",
            options=available_dataframes,
            on_change=Callbacks.reset_ss,
        )
        df = get_data(dataset)

    st.subheader("Filter Groups")
    st.button(
        "Add Group",
        on_click=Callbacks.add_group,
        key="btn_main",
        disabled=not df.shape[0],
    )
    st.divider()

    for index, group in enumerate(st.session_state["expression_groups"]):
        grp = Group.render_group(index=index, group_id=group)
        if grp:
            groups.append(grp)
if df.shape[0]:
    viewing_options = st.radio(
        "Show", options=["Source", "Filtered", "Both"], horizontal=True
    )
    if viewing_options in ["Source", "Both"]:
        with st.expander("Source", expanded=True):
            st.dataframe(df, use_container_width=True)
    if len(groups) > 0:
        filtered_df = pd.DataFrame()
        built_filters = build_filters(groups)
        try:
            exec(f"""filtered_df = {built_filters}""")
        except:
            st.warning("First expression of a group cannot be empty")
        finally:
            if viewing_options in ["Filtered", "Both"]:
                with st.expander("Filtered", expanded=True):
                    st.dataframe(filtered_df, use_container_width=True)
            with st.expander("Full Filter Logic"):
                st.code(language="python", body=BlackFormat(built_filters))
