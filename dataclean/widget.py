from __future__ import division

from abc import ABCMeta, abstractmethod
from builtins import int
from functools import wraps

import ipywidgets
import numpy as np
import pandas as pd
import matplotlib
from matplotlib import pyplot
from IPython.display import display

from dataclean.cleaning import (
    OutlierRemovalMethod,
    NullRemovalMethod,
    CategoricalTypes,
    TypeConvertMethod,
    ALLOWED_TRANSFORMATIONS
)
from dataclean.pipeline import (
    OutlierRemovalStep,
    NullRemovalStep,
    TypeConversionStep,
    RbmStep
)


def render_inactive_widget(step):
    """Return a non-interactive widget"""

    inactive_text = (
        'Currently modifying another step. '
        'Open the {} widget to modify it or '
        'click the "+" button on the pipeline widget to add a new one.'
    ).format(step.colname if hasattr(step, 'colname') else 'DataFrame')

    inactive_widget = ipywidgets.Textarea(
        value=inactive_text,
        disabled=True,
        layout=ipywidgets.Layout(width='100%')
    )

    return inactive_widget


def is_categorical(series, categorical_threshold=0.8):
    """Decide whether a pandas series is categorical or continuous"""

    type_counts = {str: 0, bool: 0}

    type_counts.update(series.dropna().apply(type).value_counts().to_dict())

    fraction_categorical = (
        (type_counts[str] + type_counts[bool])
        / sum(type_counts.values())
    ) if sum(type_counts.values()) > 0 else 0

    if (fraction_categorical >= categorical_threshold):
        categorical_type = CategoricalTypes.CATEGORICAL
    else:
        categorical_type = CategoricalTypes.CONTINUOUS

    return categorical_type


class CallbackManager(object):
    """For registering and triggering callbacks between classes"""

    def __init__(self):
        self.callbacks = []

    def send_callbacks(self, *args, **kwargs):
        for callback in self.callbacks:
            callback(*args, **kwargs)

    def register_callback(self, callback):
        self.callbacks.append(callback)


class StepWidgetControllerBase(object):
    """Widget controls to create a cleaning step"""

    __metaclass__ = ABCMeta

    def __init__(self):
        self.update_step_callback = CallbackManager()
        self.submit_step_callback = CallbackManager()

        self.tab_title = 'A title for the tab widget page'
        # this should be placed into the ALLOWED_TRANSFORMATIONS dict
        # for controls that go into the column widgets
        self.transform_type = 'A unique string or an enum class'

    def load_data(self, column, numerical_data):
        self.column = column
        self.colname = column.name
        self.numerical_data = numerical_data

    def create_widgets(self):
        """Create your control widgets"""
        self.submit_button = ipywidgets.Button(
            description='Add to Pipeline'
        )
        self.submit_button.on_click(
            lambda _: self.submit_step_callback.send_callbacks()
        )

    def reset_controls(self):
        """Reset the controls to their base state"""
        self.submit_button.description = 'Add to Pipeline'

    @abstractmethod
    def update_step(self):
        """Create a pipeline step as the controls are changed"""
        self.update_step_callback.send_callbacks()

    def _update_step(self, _):
        """For use as a widget observer"""
        return self.update_step()

    @abstractmethod
    def render_widget(self, step=None):
        """Return the overall parent widget for your controls in the state
           required to display the input step"""
        if step:
            self.submit_button.description = 'Replace Current Step'


class NullReplaceWidgetController(StepWidgetControllerBase):
    """Widget controls to create a null replacement step"""

    def __init__(self):
        super(NullReplaceWidgetController, self).__init__()
        self.tab_title = 'Nulls'
        self.transform_type = NullRemovalMethod

    def create_widgets(self):
        super(NullReplaceWidgetController, self).create_widgets()

        self.null_percent_bar = ipywidgets.FloatProgress(
            value=0,
            min=0,
            max=100,
            description='Missing:',
            disabled=False,
            continuous_update=False,
            readout=True,
            readout_format='.2g',
            layout=ipywidgets.Layout(width='400px'),
            bar_style='warning'
        )

        self.null_replace_selector = ipywidgets.Dropdown(
            options=[],
            description='Replacement Method: ',
            layout=ipywidgets.Layout(width='400px'),
            style={'description_width': 'initial'}
        )
        self.null_replace_selector.observe(
            self._update_step, names='value'
        )

        self.null_text = ipywidgets.Label()

        self.null_removal_controls = ipywidgets.VBox(
            [
                self.null_text,
                self.null_percent_bar,
                self.null_replace_selector,
                self.submit_button
            ],
            layout=ipywidgets.Layout(width='100%')
        )
        self.null_removal_controls.layout.align_items = 'center'

    def reset_controls(self, categorical_type):
        super(NullReplaceWidgetController, self).reset_controls()

        self.null_replace_selector.unobserve(self._update_step, names='value')

        self.null_text.value = "{0} of {1} ({2:.0f}%) selected".format(
            self.column.isnull().sum(),
            len(self.column),
            (
                100 * self.column.isnull().sum() / len(self.column)
            ) if len(self.column) > 0 else 0
        )

        self.null_percent_bar.bar_style = 'warning'
        self.null_percent_bar.value = (
            100 * self.column.isnull().sum() / len(self.column)
        ) if len(self.column) > 0 else 0

        allowed_transforms = {
            x.value: x for x in ALLOWED_TRANSFORMATIONS[
                categorical_type
            ] if type(x) is self.transform_type
        }

        self.null_replace_selector.options = allowed_transforms

        if len(allowed_transforms) > 0:
            self.null_replace_selector.value = self.transform_type.NONE

        self.submit_button.disabled = True
        self.null_replace_selector.observe(
            self._update_step, names='value'
        )

    def update_step(self):

        if self.null_replace_selector.value == self.transform_type.NONE:
            self.submit_button.disabled = True
            self.null_percent_bar.bar_style = 'warning'
        else:
            self.submit_button.disabled = False
            self.null_percent_bar.bar_style = 'success'

        step = NullRemovalStep(
                replacement_method=self.null_replace_selector.value,
                colname=self.colname
        )

        self.update_step_callback.send_callbacks(step)

    def render_widget(self, step=None):
        super(NullReplaceWidgetController, self).render_widget(step)
        if step:
            self.null_replace_selector.value = step.replacement_method
        return self.null_removal_controls


class OutlierReplaceWidgetController(StepWidgetControllerBase):
    """Widget controls to create an outlier replacement step"""

    def __init__(self):
        super(OutlierReplaceWidgetController, self).__init__()
        self.tab_title = 'Outliers'
        self.transform_type = OutlierRemovalMethod

    def create_widgets(self):
        super(OutlierReplaceWidgetController, self).create_widgets()
        self.outlier_range_slider = ipywidgets.FloatRangeSlider(
            value=[0, 1],
            min=0,
            max=1,
            step=0.04,
            description='Range:',
            disabled=False,
            continuous_update=False,
            readout=True,
            readout_format='.2g',
            layout=ipywidgets.Layout(width='400px'),
            style={'handle_color': 'lightblue'}
        )

        self.outlier_replace_selector = ipywidgets.Dropdown(
            options=[],
            description='Replacement Method: ',
            layout=ipywidgets.Layout(width='400px'),
            style={'description_width': 'initial'}
        )

        self.outlier_range_slider.observe(
            self._update_step, names='value'
        )
        self.outlier_replace_selector.observe(
            self._update_step, names='value'
        )
        self.cut_text = ipywidgets.Label()

        self.outlier_removal_controls = ipywidgets.VBox(
            [
                self.cut_text,
                self.outlier_range_slider,
                self.outlier_replace_selector,
                self.submit_button
            ],
            layout=ipywidgets.Layout(width='100%')
        )
        self.outlier_removal_controls.layout.align_items = 'center'

    def reset_controls(self, categorical_type):
        super(OutlierReplaceWidgetController, self).reset_controls()

        self.outlier_range_slider.unobserve(self._update_step, names='value')
        self.outlier_replace_selector.unobserve(self._update_step,
                                                names='value')

        self.cut_text.value = "{0} of {1} ({2:.0f}%) selected".format(
            0, len(self.column), 0.0
        )

        with self.outlier_range_slider.hold_trait_notifications():
            self.outlier_range_slider.min = self.numerical_data.min()
            self.outlier_range_slider.max = self.numerical_data.max()

        self.outlier_range_slider.value = [
            self.numerical_data.min(), self.numerical_data.max()
        ]

        allowed_transforms = {
            x.value: x for x in ALLOWED_TRANSFORMATIONS[categorical_type]
            if type(x) is self.transform_type
        }

        self.outlier_replace_selector.options = allowed_transforms

        if len(allowed_transforms) > 0:
            self.outlier_replace_selector.value = self.transform_type.NONE
        self.submit_button.disabled = True

        self.outlier_range_slider.observe(
            self._update_step, names='value'
        )
        self.outlier_replace_selector.observe(
            self._update_step, names='value'
        )

    def update_step(self):

        if self.outlier_replace_selector.value == self.transform_type.NONE:
            self.submit_button.disabled = True
        else:
            self.submit_button.disabled = False

        num_values_cut = self.numerical_data[
            (self.numerical_data < self.outlier_range_slider.value[0]) |
            (self.numerical_data > self.outlier_range_slider.value[1])
        ].count()

        percent_values_cut = (
            100 * num_values_cut / len(self.column)
        ) if len(self.column) > 0 else 0

        self.cut_text.value = "{0} of {1} ({2:.0f}%) selected".format(
            num_values_cut,
            len(self.column),
            percent_values_cut
        )

        step = OutlierRemovalStep(
            replacement_method=self.outlier_replace_selector.value,
            colname=self.colname,
            low_cut=self.outlier_range_slider.value[0],
            high_cut=self.outlier_range_slider.value[1]
        )

        self.update_step_callback.send_callbacks(step)

    def render_widget(self, step=None):
        super(OutlierReplaceWidgetController, self).render_widget(step)
        if step:
            self.outlier_range_slider.value = [step.low_cut, step.high_cut]
            self.outlier_replace_selector.value = step.replacement_method
        return self.outlier_removal_controls


class TypeConvertWidgetController(StepWidgetControllerBase):
    """Widget controls to create a mistyped values replacement step"""

    def __init__(self):
        super(TypeConvertWidgetController, self).__init__()
        self.transform_type = TypeConvertMethod
        self.tab_title = 'Mismatched Types'

    def load_data(self, column, numerical_data):
        super(TypeConvertWidgetController, self).load_data(
            column, numerical_data
        )
        self.type_count_dict = {float: 0, int: 0, str: 0}

        for (
            data_type, count
        ) in self.column.dropna().apply(type).value_counts().iteritems():
            self.type_count_dict[data_type] = count

    def create_widgets(self):
        super(TypeConvertWidgetController, self).create_widgets()

        self.float_percent_bar = ipywidgets.FloatProgress(
            value=0,
            min=0,
            max=100,
            description='Floats:',
            orientation='horizontal'
        )
        self.n_float = ipywidgets.Label()
        float_bar_widget = ipywidgets.HBox([self.float_percent_bar, self.n_float])

        self.int_percent_bar = ipywidgets.FloatProgress(
            value=0,
            min=0,
            max=100,
            description='Ints:',
            orientation='horizontal'
        )
        self.n_int = ipywidgets.Label()
        int_bar_widget = ipywidgets.HBox([self.int_percent_bar, self.n_int])

        self.str_percent_bar = ipywidgets.FloatProgress(
            value=0,
            min=0,
            max=100,
            description='Strings:',
            orientation='horizontal'
        )
        self.n_str = ipywidgets.Label()
        str_bar_widget = ipywidgets.HBox([self.str_percent_bar, self.n_str])

        self.type_selector = ipywidgets.Dropdown(
            options={'int': int, 'float': float, 'string': str},
            description='This column is of type:',
            layout=ipywidgets.Layout(width='300px'),
            style={'description_width': 'initial'}
        )

        self.replace_selector = ipywidgets.Dropdown(
            description='For mismatched values:',
            layout=ipywidgets.Layout(width='300px'),
            style={'description_width': 'initial'}
        )

        self.type_selector.observe(
            self._update_step, names='value'
        )
        self.replace_selector.observe(
            self._update_step, names='value'
        )

        self.widget = ipywidgets.VBox([
            float_bar_widget,
            int_bar_widget,
            str_bar_widget,
            ipywidgets.HBox([
                ipywidgets.VBox([
                    self.type_selector,
                    self.replace_selector
                ]),
                self.submit_button
            ])
        ])

        self.bar_widget_dict = {
            float: float_bar_widget,
            int: int_bar_widget,
            str: str_bar_widget
        }

    def reset_controls(self, categorical_type):
        super(TypeConvertWidgetController, self).reset_controls()
        self.type_selector.unobserve(self._update_step, names='value')
        self.replace_selector.unobserve(self._update_step, names='value')

        allowed_transforms = {
            x.value: x for x in ALLOWED_TRANSFORMATIONS[categorical_type]
            if isinstance(x, self.transform_type)
        }

        self.replace_selector.options = allowed_transforms

        if len(allowed_transforms) > 0:
            self.replace_selector.value = self.transform_type.NONE
        self.submit_button.disabled = True

        counts = reversed(sorted(
            self.type_count_dict, key=self.type_count_dict.get
        ))

        current_type = next(counts)

        while (
            current_type not in self.type_selector.options.values()
            or (
                current_type is str
                and categorical_type is CategoricalTypes.CONTINUOUS
            )
        ):
            current_type = next(counts)

        self.type_selector.value = current_type

        for dtype, widget_box in self.bar_widget_dict.items():
            widget_box.children[0].value = (
                100 * self.type_count_dict[dtype] / len(self.column)
            ) if len(self.column) > 0 else 0
            widget_box.children[0].bar_style = (
                'success' if current_type is dtype else 'warning'
            )
            widget_box.children[1].value = '{0} of {1} ({2:.0f}%)'.format(
                self.type_count_dict[dtype],
                len(self.column),
                widget_box.children[0].value
            )

        self.type_selector.observe(
            self._update_step, names='value'
        )
        self.replace_selector.observe(
            self._update_step, names='value'
        )

    def update_step(self):
        for dtype, widget_box in self.bar_widget_dict.items():
            widget_box.children[0].bar_style = (
                'success' if self.type_selector.value is dtype else 'warning'
            )
        if self.replace_selector.value == self.transform_type.NONE:
            self.submit_button.disabled = True
        else:
            self.submit_button.disabled = False

        step = TypeConversionStep(
            replacement_method=self.replace_selector.value,
            colname=self.colname,
            data_type=self.type_selector.value
        )
        self.update_step_callback.send_callbacks(step)

    def render_widget(self, step=None):
        super(TypeConvertWidgetController, self).render_widget(step)
        if step:
            self.type_selector.value = step.data_type
            self.replace_selector.value = step.replacement_method
        return self.widget


class RbmWidgetController(StepWidgetControllerBase):
    """Widget controls to create an RBM imputation step"""

    def __init__(self):
        super(RbmWidgetController, self).__init__()
        self.transform_type = 'RBM Imputation'

    def load_data(self, dataframe):
        self.dataframe = dataframe

    def create_widgets(self):

        self.submit_button = ipywidgets.Button(
            description='Add to Pipeline'
        )
        self.submit_button.on_click(
            lambda _: self.submit_step_callback.send_callbacks(self.step)
        )

        title = ipywidgets.Label(
            value='Impute missing data with '
            'a Restricted Boltzmann Machine'
        )

        self.col_list = ipywidgets.SelectMultiple(
            options=[],
            description='On columns '
        )

        self.col_list.observe(
            lambda _: self._reload_categorical_list_options(
                self.categorical_list.options,
                index=self.col_list.index
            )
        )

        self.categorical_list = ipywidgets.SelectMultiple(
            options=[],
            description=' as '
        )

        self.categorical_list.observe(
            self._change_categorical_type, names='index'
        )

        switch_categorical_type = ipywidgets.Button(description='<>')
        switch_categorical_type.on_click(
            lambda _: self._change_categorical_type({
                'old': self.categorical_list.index,
                'new': self.categorical_list.index
            })
        )

        self.widget = ipywidgets.VBox([
            title,
            ipywidgets.HBox([
                self.col_list,
                self.categorical_list,
                switch_categorical_type
            ]),
            ipywidgets.VBox([
                self.submit_button,
                ipywidgets.Label(
                        value='(Until you execute or export your pipeline, '
                        'RBM imputed values are placeholders only.)'
                )
            ])
        ])

    def _reload_categorical_list_options(self, options, index=()):
        self.categorical_list.unobserve(
            self._change_categorical_type, names='index'
        )
        self.categorical_list.options = self._format_list(options)
        self.categorical_list.index = index
        self.categorical_list.observe(
            self._change_categorical_type, names='index'
        )
        self.update_step()

    def _change_categorical_type(self, index):
        old_index = index['old']

        options = list(self.categorical_list.options)
        indices_to_change = index['new']

        for index in indices_to_change:
            if options[index].strip() == CategoricalTypes.CONTINUOUS.value:
                options[index] = CategoricalTypes.CATEGORICAL.value
            elif options[index].strip() == CategoricalTypes.CATEGORICAL.value:
                options[index] = CategoricalTypes.CONTINUOUS.value

        self._reload_categorical_list_options(options, index=old_index)

    def _format_list(self, input_list):
        # workaround - ensures unique values go into Select widget even though
        # we just want multiple instances of "categorical" and "continuous"
        output_list = []
        for i, item in enumerate(input_list):
            output_list.append(item.strip() + ' ' * i)
        return output_list

    def reset_controls(self):
        super(RbmWidgetController, self).reset_controls()
        self.col_list.options = self.dataframe.columns.tolist()
        categorical_list = []

        for col in self.col_list.options:
            categorical_list.append(is_categorical(self.dataframe[col]).value)

        self.col_list.value = ()
        self.col_list.rows = self.categorical_list.rows = len(categorical_list)

        self._reload_categorical_list_options(categorical_list)

    def update_step(self):

        numerical_columns = []
        categorical_columns = []

        for i in self.col_list.index:
            categorical_type = self.categorical_list.options[i].strip()
            if categorical_type == CategoricalTypes.CONTINUOUS.value:
                numerical_columns.append(self.col_list.options[i])
            elif categorical_type == CategoricalTypes.CATEGORICAL.value:
                categorical_columns.append(self.col_list.options[i])

        self.step = RbmStep(
            numerical_columns=numerical_columns,
            categorical_columns=categorical_columns
        )

    def render_widget(self, step=None):
        super(RbmWidgetController, self).render_widget(step)

        widget = self.widget

        if isinstance(step, RbmStep):
            self.col_list.value = (
                step.numerical_columns + step.categorical_columns
            )

            categorical_list = []

            for col in self.col_list.options:
                if col in step.numerical_columns:
                    categorical_list.append(
                        CategoricalTypes.CONTINUOUS.value
                    )
                elif col in step.categorical_columns:
                    categorical_list.append(
                        CategoricalTypes.CATEGORICAL.value
                    )
                else:
                    categorical_list.append(
                        is_categorical(self.dataframe[col]).value
                    )

            self._reload_categorical_list_options(
                categorical_list,
                index=self.col_list.index
            )
            self.step = step
        elif step:
            widget = render_inactive_widget(step)

        return widget


def _noninteractive(func):
    """Ensure plots are created in non-interactive mode with seaborn style."""

    @wraps(func)
    def noninteractive_wrapper(*args, **kwargs):
        mpl_interactivity = matplotlib.is_interactive()
        matplotlib.interactive(False)

        with pyplot.style.context('seaborn'):
            rval = func(*args, **kwargs)

        matplotlib.interactive(mpl_interactivity)
        return rval

    return noninteractive_wrapper


class PlotWidgetController(object):
    """Widget controls to display and update plots for dataframe columns."""

    gs_one_plot = matplotlib.gridspec.GridSpec(1, 1)
    gs_two_plots = matplotlib.gridspec.GridSpec(
        2, 1, height_ratios=[1, 1], hspace=0.1
    )

    CUT_LINE_COLOUR = 'red'
    CUT_BINS_COLOUR = 'orange'

    def __init__(self):
        self.output_widget = ipywidgets.Output(
            layout=ipywidgets.Layout(
                min_width='300px',
                height='160px'
            )
        )
        self.create_figure()

    def load_data(self, column, numerical_data):
        self.column = column
        self.colname = column.name
        self.numerical_data = numerical_data

    @_noninteractive
    def create_figure(self):
        self.fig = pyplot.figure()

        self.ax_main = self.fig.add_subplot(self.gs_two_plots[0])

        self.ax_mod = self.fig.add_subplot(
            self.gs_two_plots[1]
        )

        pyplot.setp(self.ax_mod.get_xticklabels(), visible=False)
        pyplot.setp(self.ax_mod.get_yticklabels(), visible=False)

        self.ax_cut = self.ax_main.twinx()

        # enforces desired drawing order
        self.ax_mod.set_zorder(1)
        self.ax_main.set_zorder(2)
        self.ax_cut.set_zorder(3)

        self.ax_cut.get_xaxis().set_visible(False)
        self.ax_cut.get_yaxis().set_visible(False)

        self.ax_main.tick_params(axis='y', which='major', labelsize=12)
        self.ax_mod.tick_params(axis='y', which='major', labelsize=12)

    def display_figure(self):
        self.output_widget.clear_output(wait=True)

        # Magic numbers came from testing using categorical columns
        # with large numbers of categories
        fig_width = 0.1 * len(self.ax_main.get_xticks()) + 3.5
        fig_height = 2.4
        self.fig.set_size_inches(fig_width, fig_height)

        self.output_widget.layout.width = '{}px'.format(fig_width*70)
        self.output_widget.layout.height = '{}px'.format(fig_height*80)

        if self.categorical_type is CategoricalTypes.CONTINUOUS:
            self.ax_main.xaxis.set_major_locator(
                matplotlib.ticker.AutoLocator()
            )

        with self.output_widget:
            display(self.fig)

    def reset_plots(self, categorical_type):
        self.categorical_type = categorical_type
        self.draw_main_plot()
        self.update_plots()

    @_noninteractive
    def draw_main_plot(self):
        self.ax_main.clear()
        self.ax_mod.clear()

        if self.categorical_type is CategoricalTypes.CATEGORICAL:
            col = self.column.dropna().value_counts()
            col.index = col.index.format()
            if len(col) > 0:
                col.sort_index().plot(
                    kind='bar',
                    ax=self.ax_main,
                    alpha=0.4
                )
        else:
            hist_orig, self.bins = np.histogram(self.numerical_data)
            self.bin_width = self.bins[1]-self.bins[0]

            margin = (
                self.bins[-1] - self.bins[0]
            ) * self.ax_main.margins()[0]

            self.ax_main.set_xlim(
                (self.bins[0] - margin, self.bins[-1] + margin)
            )

            self.ax_main.bar(
                self.bins[:-1],
                hist_orig,
                width=self.bin_width,
                align='edge',
                alpha=0.4
             )

        self.ymax = self.ax_main.get_ylim()[1]
        self.low_cut_line, = self.ax_main.plot(
            [None, None],
            [self.ymax, 0],
            color=self.CUT_LINE_COLOUR,
        )

        self.high_cut_line, = self.ax_main.plot(
            [None, None],
            [self.ymax, 0],
            color=self.CUT_LINE_COLOUR,
        )


    def update_plots(self, step=None, col_mod=None):
        if isinstance(step, OutlierRemovalStep):
            self.low_cut_line.set_xdata([[step.low_cut, step.low_cut]])
            self.high_cut_line.set_xdata([[step.high_cut, step.high_cut]])
            self.draw_cut_plot(step.low_cut, step.high_cut)
        else:
            self.hide_cut_plot()

        self.draw_modified_plot(
            col_mod if col_mod is not None else self.column
        )

        self.display_figure()

    @_noninteractive
    def draw_modified_plot(self, col_mod):
        self.ax_mod.clear()

        data_mod = col_mod.loc[col_mod.apply(
            lambda x:
                isinstance(x, (int, float))
        )]
        data_mod = data_mod.dropna()
        col_mod = col_mod.dropna().value_counts()

        if (
            self.categorical_type is CategoricalTypes.CATEGORICAL
            and not self.column.dropna().value_counts().equals(col_mod)
        ):
            self.ax_main.set_position(
                self.gs_two_plots[0].get_position(self.fig)
            )
            self.ax_cut.set_position(
                self.gs_two_plots[0].get_position(self.fig)
            )

            pyplot.setp(self.ax_main.get_xticklabels(), visible=False)
            pyplot.setp(self.ax_mod.get_xticklabels(), visible=True)
            pyplot.setp(self.ax_mod.get_yticklabels(), visible=True)

            col_orig = self.column.dropna().value_counts()

            col_mod.index = col_mod.index.format()
            col_orig.index = col_orig.index.format()

            col_delta = col_mod.sub(col_orig, fill_value=0)
            col_delta = col_delta[col_delta > 0]

            col_mod = col_mod.sub(col_delta, fill_value=0)

            col_mod = pd.concat([col_mod, col_delta], axis=1)

            col_mod.sort_index().plot(
                kind='bar',
                ax=self.ax_mod,
                alpha=0.4,
                stacked=True,
                legend=False
            )

        elif (
            self.categorical_type is not CategoricalTypes.CATEGORICAL
            and not data_mod.equals(self.numerical_data)
        ):
            self.ax_main.set_position(
                self.gs_two_plots[0].get_position(self.fig)
            )
            self.ax_cut.set_position(
                self.gs_two_plots[0].get_position(self.fig)
            )

            pyplot.setp(self.ax_main.get_xticklabels(), visible=False)
            pyplot.setp(self.ax_mod.get_xticklabels(), visible=True)
            pyplot.setp(self.ax_mod.get_yticklabels(), visible=True)

            hist_mod, _ = np.histogram(data_mod, self.bins)
            hist_orig, _ = np.histogram(self.numerical_data, self.bins)

            hist_delta = hist_mod - hist_orig
            hist_delta[hist_delta < 0] = 0

            self.ax_mod.bar(
                self.bins[:-1],
                hist_mod-hist_delta,
                width=self.bin_width,
                align='edge',
                alpha=0.4
            )
            self.ax_mod.bar(
                self.bins[:-1],
                hist_delta,
                width=self.bin_width,
                color='g',
                bottom=hist_mod - hist_delta,
                align='edge',
                alpha=0.4
            )
        else:
            self.ax_main.set_position(
                self.gs_one_plot[0].get_position(self.fig)
            )
            self.ax_cut.set_position(
                self.gs_one_plot[0].get_position(self.fig)
            )
            pyplot.setp(self.ax_main.get_xticklabels(), visible=True)
            pyplot.setp(self.ax_mod.get_xticklabels(), visible=False)
            pyplot.setp(self.ax_mod.get_yticklabels(), visible=False)

    @_noninteractive
    def draw_cut_plot(self, low_cut, high_cut):
        self.ax_cut.set_visible(True)

        ticks = self.ax_cut.get_xticks()
        self.ax_cut.clear()
        self.ax_cut.set_xticks(ticks)

        cut_data = self.numerical_data.loc[self.numerical_data.apply(
            lambda x:
                x < low_cut or
                x > high_cut
        )]

        hist_cut, _ = np.histogram(cut_data, self.bins)

        self.ax_cut.bar(
            self.bins[:-1],
            hist_cut,
            width=self.bin_width,
            align='edge',
            color=self.CUT_BINS_COLOUR,
            alpha=0.4
        )

        self.ax_cut.set_ylim(self.ax_main.get_ylim())

    def hide_cut_plot(self):
        self.low_cut_line.set_xdata([[None, None]])
        self.high_cut_line.set_xdata([[None, None]])
        self.ax_cut.set_visible(False)

    def render_widget(self):
        if self.fig:
            pyplot.close(self.fig)
        self.create_figure()

        return self.output_widget


class ColumnWidgetController(object):
    """Container widget for column-specific step creation control widgets"""

    def __init__(self):

        self.widget = None
        self.step_being_modified = None
        self.new_step_callback = CallbackManager()
        self.modify_step_callback = CallbackManager()
        self.active_callback = self.new_step_callback
        self.categorical_type = None

        self.plot_widget_controller = PlotWidgetController()

        def update_active_step(new_step):
            self.active_step = new_step
            col_mod = new_step.execute(self.dataframe)[self.colname]
            self.redraw_preview(col_mod)
            self.plot_widget_controller.update_plots(new_step, col_mod)

        self.step_creation_controls = [
            NullReplaceWidgetController(),
            OutlierReplaceWidgetController(),
            TypeConvertWidgetController()
        ]

        self.controls_dict = {}

        for controller in self.step_creation_controls:
            self.controls_dict[controller.transform_type] = controller
            controller.update_step_callback.register_callback(
                update_active_step
            )

        self.create_widgets()

    def create_widgets(self):

        self.categorical_selector = ipywidgets.Dropdown(
            options={
                cat_type.value: cat_type for cat_type in CategoricalTypes
            },
            layout=ipywidgets.Layout(width='80%')
        )

        self.plot_widget_container = ipywidgets.VBox(
            [
                self.plot_widget_controller.render_widget(),
                self.categorical_selector
            ],
            layout=ipywidgets.Layout(
                width='350px',
                height='220px',
                overflow_x='scroll',
                overflow_y='auto'
            )
        )

        self.plot_widget_container.layout.align_items = 'flex-start'

        self.categorical_selector.observe(
            self.categorical_selector_onchange, names='value'
        )

        self.preview_widget = ipywidgets.HTML()
        self.preview_widget_container = ipywidgets.VBox([
            ipywidgets.Label(value='Current Step'),
            self.preview_widget
        ], layout=ipywidgets.Layout(max_height='200px'))

        self.tab_widget = ipywidgets.Tab(
            layout=ipywidgets.Layout(
                overflow_x='scroll',
                width='600px',
                height='90%'
            )
        )

        self.tab_widget.observe(
            self.tab_widget_onchange, names='selected_index'
        )

        for controller in self.step_creation_controls:
            controller.create_widgets()

            controller.submit_step_callback.register_callback(
                lambda: self.active_callback.send_callbacks(self.active_step)
            )

        self.widget = ipywidgets.HBox(
            [
                self.plot_widget_container,
                self.tab_widget,
                self.preview_widget_container
            ],
            layout=ipywidgets.Layout(
                display='flex',
                align_items='stretch',
                width='100%',
                height='220px'
            )
        )

    def tab_widget_onchange(self, _):
        index = self.tab_widget.selected_index

        for controller in self.controls_dict.values():
            if controller.tab_title == self.tab_widget.get_title(index):
                controller.update_step()

    def categorical_selector_onchange(self, _):
        self.categorical_type = self.categorical_selector.value

        self.active_step = NullRemovalStep(
            replacement_method=NullRemovalMethod.NONE,
            colname=self.colname
        )

        self.reset_controls()

    def load_data(self, series, dataframe, step=None):
        self.dataframe = dataframe
        self.column = series
        self.colname = series.name

        if not self.categorical_type:
            self.categorical_type = is_categorical(series)

        self.numerical_data = series.loc[series.apply(
            lambda x:
                isinstance(x, (int, float))
        )]

        self.numerical_data = self.numerical_data.dropna()

        for controller in self.step_creation_controls:
            controller.load_data(
                column=self.column,
                numerical_data=self.numerical_data
            )
        self.plot_widget_controller.load_data(
                column=self.column,
                numerical_data=self.numerical_data
            )

        self.redraw_preview()
        self.step_being_modified = step

    def redraw_preview(self, col_modified=None):

        if col_modified is not None:
            col_mod = col_modified.reindex(
                index=self.column.index,
                fill_value='<br>'
            )
        else:
            col_mod = self.column

        self.preview_widget.value = '<center>This Step</center>' + pd.concat(
            [self.column.rename('before'), col_mod.rename('after')],
            axis=1
        ).style.set_table_attributes('class="table"').render()

    def render_widget(self):
        self.reset_controls()
        self.redraw_preview()

        if self.step_being_modified:
            self.set_controls_for_step(self.step_being_modified)

        return self.widget

    def reset_controls(self):
        self.tab_widget.unobserve(
            self.tab_widget_onchange, names='selected_index'
        )
        self.categorical_selector.unobserve(
            self.categorical_selector_onchange, names='value'
        )

        self.active_callback = self.new_step_callback

        tab_children = []
        tab_titles = []

        allowed_transforms = set(
            transform if isinstance(transform, str) else type(transform)
            for transform in ALLOWED_TRANSFORMATIONS[self.categorical_type]
        )

        for transform_type in sorted(allowed_transforms, key=str):
            tab_children.append(
                self.controls_dict[transform_type].render_widget()
            )
            tab_titles.append(
                self.controls_dict[transform_type].tab_title
            )

        self.tab_widget.children = tuple(tab_children)

        for i in range(len(tab_children)):
            self.tab_widget.set_title(i, tab_titles[i])

        self.tab_widget.selected_index = 0

        self.active_step = NullRemovalStep(
            replacement_method=NullRemovalMethod.NONE,
            colname=self.colname
        )

        for controller in self.step_creation_controls:
            controller.reset_controls(
                categorical_type=self.categorical_type
            )

        self.categorical_selector.disabled = False
        self.categorical_selector.value = self.categorical_type

        self.plot_widget_controller.reset_plots(
            self.categorical_type
        )

        self.tab_widget.observe(
            self.tab_widget_onchange, names='selected_index'
        )
        self.categorical_selector.observe(
            self.categorical_selector_onchange, names='value'
        )

    def set_controls_for_step(self, step):

        if hasattr(step, 'colname') and step.colname == self.colname:

            while (
                step.replacement_method
                not in ALLOWED_TRANSFORMATIONS[self.categorical_type]
            ):
                self.categorical_selector.index = (
                    self.categorical_selector.index + 1
                ) % len(self.categorical_selector.options)

            self.tab_widget.children = [
                self.controls_dict[
                    type(step.replacement_method)
                ].render_widget(step)
            ]

            self.active_callback = self.modify_step_callback
            self.tab_widget.set_title(0, 'Modifying Current Step')
            self.tab_widget.selected_index = 0
        else:
            self.tab_widget.children = [render_inactive_widget(step)]

            self.tab_widget.set_title(0, str(self.colname))
        self.categorical_selector.disabled = True


class DataFrameWidgetController(object):
    """Container widget for dataframe-wide controls and the pipeline"""

    def __init__(self, pipeline_widget, sampled_rows):
        self.resample_callback = CallbackManager()
        self.new_step_callback = CallbackManager()
        self.modify_step_callback = CallbackManager()

        self.active_callback = self.new_step_callback

        self.rbm_widget_controller = RbmWidgetController()
        self.rbm_widget_controller.create_widgets()

        def submit_rbm_step(*args, **kwargs):
            self.active_callback.send_callbacks(*args, **kwargs)

        self.rbm_widget_controller.submit_step_callback.register_callback(
            submit_rbm_step
        )

        self.pipeline_widget_container = ipywidgets.Accordion(
            children=[pipeline_widget]
        )
        self.pipeline_widget_container.set_title(0, "Pipeline")
        self.pipeline_widget_container.selected_index = None
        self.preview_widget = ipywidgets.Output(
            layout=ipywidgets.Layout(
                    overflow_y='scroll',
                    overflow_x='scroll',
                    width='100%',
                    height='190px'
            )
        )

        self.rbm_widget_container = ipywidgets.Accordion(
            children=[self.rbm_widget_controller.render_widget()]
        )
        self.rbm_widget_container.set_title(0, "Restricted Boltzmann Machine")
        self.rbm_widget_container.selected_index = None

        self.preview_widget_container = ipywidgets.Accordion(
            children=[self.preview_widget]
        )
        self.preview_widget_container.set_title(0, "DataFrame Preview")
        self.preview_widget_container.selected_index = None

        child_widgets = [
            self.preview_widget_container,
            self.rbm_widget_container,
            self.pipeline_widget_container,
            ipywidgets.Label(
                'Click on a column name below to start adding steps.'
            )
        ]

        if sampled_rows:
            sample_label = ipywidgets.Label(
                value='Viewing {} sampled rows from your dataframe.'.format(
                    sampled_rows
                )
            )
            sample_btn = ipywidgets.Button(description='Resample')
            sample_btn.on_click(
                lambda _: self.resample_callback.send_callbacks()
            )
            child_widgets = (
                [ipywidgets.HBox([sample_label, sample_btn])] + child_widgets
            )

        self.widget = ipywidgets.VBox(child_widgets)

    def _redraw_preview(self, dataframe):
        self.preview_widget.clear_output(wait=True)
        with self.preview_widget:
            display(dataframe.style.set_caption(
               'Preview up to the current pipeline step'
            ))

    def render_widget(self, dataframe, step=None):
        self.dataframe = dataframe
        self._redraw_preview(dataframe)
        self.rbm_widget_controller.load_data(dataframe)
        self.rbm_widget_controller.reset_controls()
        self.rbm_widget_container.children = tuple([
            self.rbm_widget_controller.render_widget(step)
        ])

        # if we are currently modifying a non column-specific step
        if step and not hasattr(step, 'colname'):
            self.active_callback = self.modify_step_callback
        else:
            self.active_callback = self.new_step_callback

        return self.widget

    def display_pipeline(self):
        self.pipeline_widget_container.selected_index = 0


class PipelineWidgetController(object):
    """Container widget for a view of the processing pipeline"""

    CAROUSEL_LAYOUT = ipywidgets.Layout(
        overflow_x='scroll',
        width='800px',
        height='',
        flex_direction='row',
        display='flex'
    )

    def __init__(self, pipeline, name):

        self.pipeline = pipeline
        self.name = name
        self.pipeline_view = ipywidgets.Box(
            children=[], layout=self.CAROUSEL_LAYOUT
        )
        self.info_label = ipywidgets.Label(value='')
        self.info_label.layout.height = '30px'

        self.add_button = ipywidgets.Button(description='+')
        self.add_button.layout.visibility = 'hidden'
        self.add_button.on_click(lambda _: self._enter_add_mode())

        self.add_mode_callback = CallbackManager()
        self.edit_mode_callback = CallbackManager()
        self.delete_step_callback = CallbackManager()
        self.execute_callback = CallbackManager()
        self.export_callback = CallbackManager()

        self.execute_button = ipywidgets.Button(description='Execute Pipeline')
        self.execute_button.on_click(lambda _: self._execute_pipeline())

        self.export_button = ipywidgets.Button(description='Export to Code')
        self.export_button.on_click(lambda _: self._export_pipeline())

    def render_widget(self, active_step=None):

        children = []
        self.pipeline_step_widgets = []
        self.display_message('Add a step to get started')

        for step in self.pipeline.steps:
            pipeline_step_widget = PipelineStepWidgetController(step)

            pipeline_step_widget.modify_step_callback.register_callback(
                self._enter_edit_mode
            )

            pipeline_step_widget.stop_modifying_callback.register_callback(
                self._enter_add_mode
            )

            pipeline_step_widget.delete_step_callback.register_callback(
                self._delete_step
            )

            self.pipeline_step_widgets.append(pipeline_step_widget)
            children.append(pipeline_step_widget.widget)

        if children:
            children.append(
                ipywidgets.VBox(
                    [
                        self.add_button,
                        self.execute_button,
                        self.export_button
                    ],
                    layout=ipywidgets.Layout(min_width='150px')
                )
            )
            self.display_message('')

        self.pipeline_view.children = tuple(children)
        self.widget = ipywidgets.VBox([self.pipeline_view, self.info_label])
        self._enter_edit_mode(active_step)

        return self.widget

    def _enter_edit_mode(self, step):
        if step:
            self.add_button.layout.visibility = None # this means it's visible!
            for pipeline_step_widget in self.pipeline_step_widgets:
                if pipeline_step_widget.step is step:
                    pipeline_step_widget._set_active_style()
                else:
                    pipeline_step_widget._set_inactive_style()
            self.edit_mode_callback.send_callbacks(step)
            message = 'Modifying step'
            if hasattr(step, 'colname'):
                message += ' on column ' + str(step.colname)
            self.display_message(message)
        else:
            self.add_button.layout.visibility = 'hidden'

    def _export_pipeline(self):
        self.display_message('Exported to code cell.')
        self.export_callback.send_callbacks()

    def _execute_pipeline(self):
        self.display_message(
                    'Executing pipeline... '
        )

        self.execute_callback.send_callbacks()

        self.display_message(
            'Cleaned DataFrame output to "'
            + self.name + '_cleaned". '
            + 'Reload DataCleaner to refresh list.'
        )

    def _delete_step(self, step):
        self.add_button.layout.visibility = 'hidden'
        self.delete_step_callback.send_callbacks(step)

    def _enter_add_mode(self):
        self.add_button.layout.visibility = 'hidden'
        for pipeline_step_widget in self.pipeline_step_widgets:
            pipeline_step_widget._set_inactive_style()
        self.add_mode_callback.send_callbacks()
        self.display_message('')

    def display_message(self, message):
        self.info_label.value = message


class PipelineStepWidgetController(object):
    """Container widget for a single step of the processing pipeline"""

    def __init__(self, step):

        select_box = ipywidgets.Select(
            options=step.description.replace(', ', '\n').splitlines(),
            rows=3,
            disabled=False,
            layout=ipywidgets.Layout(width='200px')
        )

        self.modify_button = ipywidgets.ToggleButton(
            layout=ipywidgets.Layout(height='25px', width='98%')
        )

        self.delete_button = ipywidgets.Button(
            description='Delete Step',
            layout=ipywidgets.Layout(
                height='25px', width='98%', visibility='hidden'
            ),
            button_style='warning'
        )

        self.widget = ipywidgets.VBox(
            [
                self.modify_button,
                select_box,
                self.delete_button
            ],
            layout=ipywidgets.Layout(min_width='200px')
        )

        self.step = step
        self.modify_step_callback = CallbackManager()
        self.stop_modifying_callback = CallbackManager()
        self.delete_step_callback = CallbackManager()

        self.modify_button.observe(self._modify_button_on_click, names='value')
        self.delete_button.on_click(
            lambda _: self.delete_step_callback.send_callbacks(self.step)
        )

        self._set_inactive_style()

    def _modify_button_on_click(self, value):
        if value['new'] is True:
            self.modify_step_callback.send_callbacks(self.step)
        else:
            self.stop_modifying_callback.send_callbacks()

    def _set_active_style(self):
        self.modify_button.button_style = 'primary'
        self.modify_button.description = 'Modifying'
        self.modify_button.value = True
        self.delete_button.layout.visibility = None  # This means visible.

    def _set_inactive_style(self):
        self.modify_button.button_style = ''
        self.modify_button.description = 'Modify'

        self.modify_button.unobserve(
            self._modify_button_on_click, names='value'
        )
        self.modify_button.value = False
        self.modify_button.observe(
            self._modify_button_on_click, names='value'
        )

        self.delete_button.layout.visibility = 'hidden'
