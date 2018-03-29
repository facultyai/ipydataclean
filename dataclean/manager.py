import json
import sys
from base64 import b64encode

import ipywidgets
from IPython.display import Javascript, display
from IPython.utils.py3compat import str_to_bytes, bytes_to_str
from pandas import DataFrame

from dataclean.pipeline import Pipeline
from dataclean.widget import (
    CallbackManager,
    ColumnWidgetController,
    DataFrameWidgetController,
    PipelineWidgetController
)


def create_new_code_cell(code):
    """Javascript to create and populate a new code cell in the notebook"""
    encoded_code = bytes_to_str(b64encode(str_to_bytes(code)))
    display(Javascript("""
        var code_cell = IPython.notebook.insert_cell_below('code');
        code_cell.set_text(atob("{0}"));
    """.format(encoded_code)))


def display_colwidget(col_id):
    """Javascript to display a collapsed column widget"""
    display(Javascript("""
        if ($('#{0}_row').hasClass('hidden')){{$('#{0}').click()}}
    """.format(str(col_id))))


class DataCleaner(object):
    """Keeps track of DataFrames in the user's kernel"""

    def __init__(self):
        self.dataframe_managers = {}
        self._main = sys.modules['__main__']
        self.refresh()

    def refresh(self):
        dataframe_managers_new = {}
        for var_name, var in vars(self._main).items():
            if isinstance(var, DataFrame) and not var_name.startswith('_'):
                manager = self._manager_for_dataframe(var, var_name)
                dataframe_managers_new[id(var)] = manager

        self.dataframe_managers = dataframe_managers_new

    def dataframe_metadata(self):
        self.refresh()
        metadata = []
        for manager in self.dataframe_managers.values():
            metadata.append(manager.metadata())
        return json.dumps(metadata)

    def manager_for_id(self, dataframe_id):
        return self.dataframe_managers[dataframe_id]

    def _manager_for_dataframe(self, dataframe, name):
        for manager in self.dataframe_managers.values():
            if manager.full_dataframe is dataframe:
                manager.name = name
                break
        else:
            manager = DataframeManager(dataframe, name)

            def export_cleaned_dataframe(new_dataframe, dataframe_name):
                new_df_name = dataframe_name + '_cleaned'
                suffix = 0

                # ensures we have a unique name
                while getattr(self._main, new_df_name, None) is not None:
                    suffix += 1
                    new_df_name = dataframe_name + '_cleaned_' + str(suffix)

                setattr(self._main, new_df_name, new_dataframe)

            def export_to_code(code):
                create_new_code_cell(code)

            manager.execute_callback.register_callback(
                export_cleaned_dataframe
            )
            manager.export_callback.register_callback(
                export_to_code
            )

        return manager


class DataframeManager(object):
    """Manages the widget controller classes for a single DataFrame"""

    MAX_ROWS = 1000

    def __init__(self, dataframe, name):
        self.name = name
        self.column_widget_controller_by_id = {}
        self._pipeline_widget_controller = None
        self._dataframe_widget_controller = None

        self.execute_callback = CallbackManager()
        self.export_callback = CallbackManager()

        self.full_dataframe = dataframe

        if dataframe.shape[0] > self.MAX_ROWS:
            self.dataframe = dataframe.sample(n=self.MAX_ROWS)
            self.is_sample = True
        else:
            self.dataframe = dataframe
            self.is_sample = False

        if not(dataframe.columns.is_unique and dataframe.index.is_unique):
            self.dataframe = DataFrame({'_':[]})

        self.pipeline = Pipeline()
        self.active_step = None

        self.column_by_id = {}
        for colname, column in self.dataframe.items():
            self.column_by_id[id(column)] = self.dataframe[colname]

    def metadata(self):
        metadata = {
            'dfName': self.name,
            'dfId': id(self.full_dataframe),
            'dfShape': self.full_dataframe.shape,
            'dfColnames': sorted(
                self.full_dataframe.columns.to_series().apply(str)
            ),
            'dfCols': [{
                'colname': colname,
                'colId': id(self.full_dataframe[colname]),
                'description': {
                    'dtype': str(column.dtype),
                    'null_percentage': "{0:.0f}%".format(
                        100 * column.isnull().sum()
                        / float(len(column)) if len(column) > 0 else 0
                    ),
                    'distinct': len(column.value_counts())
                }
            } for colname, column in self.full_dataframe.items()]
        }
        return metadata

    @property
    def dataframe_widget(self):
        if self._dataframe_widget_controller is None:
            self._dataframe_widget_controller = DataFrameWidgetController(
                self.pipeline_widget,
                self.MAX_ROWS if self.is_sample else 0
            )

            def resample():
                self.dataframe = self.full_dataframe.sample(n=self.MAX_ROWS)
                self._refresh_colwidgets()

            self._dataframe_widget_controller.resample_callback \
                .register_callback(resample)
            self._dataframe_widget_controller.new_step_callback \
                .register_callback(self._new_step)
            self._dataframe_widget_controller.modify_step_callback \
                .register_callback(self._replace_active_step)

        if self.dataframe.equals(DataFrame({'_':[]})):
            widget = ipywidgets.Label(
                value=(
                    'DataFrames with non-unique column names or index are '
                    'unsupported.'
                ),
                layout=ipywidgets.Layout(width='600px')
            )
        elif self.dataframe.empty:
            widget = ipywidgets.Label(
                value=(
                    'DataFrame is empty.'
                )
            )
        else:
            widget = self._dataframe_widget_controller.render_widget(
            self.dataframe, self.active_step
        )

        return widget


    @property
    def pipeline_widget(self):
        if self._pipeline_widget_controller is None:
            self._pipeline_widget_controller = PipelineWidgetController(
                self.pipeline, self.name
            )

            def enter_edit_mode(active_step):
                self._refresh_colwidgets(step=active_step)
                self.active_step = active_step
                if hasattr(active_step, 'colname'):
                    display_colwidget(
                        id(self.full_dataframe[active_step.colname])
                    )

            def enter_add_mode():
                self._refresh_colwidgets()
                self.active_step = None

            def execute_pipeline():
                new_dataframe = self.pipeline.execute(
                    self.full_dataframe.copy(),
                    preview=False
                )
                self.execute_callback.send_callbacks(new_dataframe, self.name)

            def export_pipeline():
                code = self.pipeline.export()
                self.export_callback.send_callbacks(code)

            self._pipeline_widget_controller.add_mode_callback \
                .register_callback(enter_add_mode)
            self._pipeline_widget_controller.edit_mode_callback \
                .register_callback(enter_edit_mode)

            self._pipeline_widget_controller.execute_callback \
                .register_callback(execute_pipeline)
            self._pipeline_widget_controller.export_callback \
                .register_callback(export_pipeline)

            self._pipeline_widget_controller.delete_step_callback \
                .register_callback(self._delete_step)

        return self._pipeline_widget_controller.render_widget(self.active_step)

    def column_widget(self, col_id):
        if self.dataframe.empty:
            widget = ipywidgets.Label(value='')
        else:
            if col_id in self.column_widget_controller_by_id:
                col_widget_controller = (
                    self.column_widget_controller_by_id[col_id]
                )
            else:
                column = self.column_by_id[col_id]

                col_widget_controller = ColumnWidgetController()
                col_widget_controller.load_data(
                    column, self.dataframe, self.active_step
                )

                self.column_widget_controller_by_id[col_id] = (
                    col_widget_controller
                )

                col_widget_controller.new_step_callback \
                    .register_callback(self._new_step)
                col_widget_controller.modify_step_callback \
                    .register_callback(self._replace_active_step)

            widget = col_widget_controller.render_widget()

        return widget

    def _refresh_colwidgets(self, step=None):
        new_dataframe = self.pipeline.execute(
            self.dataframe, up_to_step=step
        )
        for (
            col_id, col_widget_controller
        ) in self.column_widget_controller_by_id.items():
            col_widget_controller.load_data(
                new_dataframe[self.column_by_id[col_id].name],
                new_dataframe,
                step
            )
            col_widget_controller.render_widget()
        self._dataframe_widget_controller.render_widget(new_dataframe, step)

    def _new_step(self, new_step):
        self.pipeline.append(new_step)
        if self._pipeline_widget_controller:
            self._pipeline_widget_controller.render_widget()
            self._dataframe_widget_controller.display_pipeline()
        self._refresh_colwidgets()

    def _replace_active_step(self, modified_step):
        self.pipeline.replace(self.active_step, modified_step)
        self.active_step = None
        if self._pipeline_widget_controller:
            self._pipeline_widget_controller.render_widget()
            self._dataframe_widget_controller.display_pipeline()
        self._refresh_colwidgets()

    def _delete_step(self, step):
        self.pipeline.remove(step)
        self._pipeline_widget_controller.render_widget()
        self.active_step = None
        self._refresh_colwidgets()
