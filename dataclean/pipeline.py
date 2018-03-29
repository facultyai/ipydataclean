from abc import ABCMeta, abstractproperty

import boltzmannclean

import dataclean.codegen as codegen
from dataclean.cleaning import (
    OUTLIER_REMOVAL_METHODS,
    NULL_REMOVAL_METHODS,
    TYPE_CONVERT_METHODS
)


class DataCleanStepBase(object):
    """Base class for a cleaning step to be applied to a dataframe"""

    __metaclass__ = ABCMeta

    def __init__(self, **params):
        self.params = params

    @abstractproperty
    def cleaning_function(self):
        pass

    def execute(self, dataframe, preview=True):
        return self.cleaning_function(
            dataframe.copy() if preview else dataframe,
            **self.params
        )

    @abstractproperty
    def description(self):
        """Return a human readable brief description of the step"""
        pass

    def render_code(self):
        return codegen.render_code(
            function=self.cleaning_function,
            code_comment=self.description,
            **self.params
        )

    def required_import_statements(self):
        return codegen.get_module_dependencies(self.cleaning_function)


class OutlierRemovalStep(DataCleanStepBase):
    """A step to handle outliers in a numerical dataframe column"""

    def __init__(self, **params):
        super(OutlierRemovalStep, self).__init__(**params)
        self.colname = self.params['colname']
        self.low_cut = self.params['low_cut']
        self.high_cut = self.params['high_cut']
        self.replacement_method = self.params.pop('replacement_method')

    @property
    def cleaning_function(self):
        return OUTLIER_REMOVAL_METHODS[self.replacement_method]

    @property
    def description(self):
        description = (
            'On {colname}, '
            'for values outside {low_cut} to {high_cut}, {replacement_method}'
        ).format(
            colname=self.colname,
            low_cut=self.low_cut,
            high_cut=self.high_cut,
            replacement_method=self.replacement_method.value
        )

        return description


class NullRemovalStep(DataCleanStepBase):
    """A step to handle null values in a dataframe column"""

    def __init__(self, **params):
        super(NullRemovalStep, self).__init__(**params)
        self.colname = self.params['colname']
        self.replacement_method = self.params.pop('replacement_method')

    @property
    def cleaning_function(self):
        return NULL_REMOVAL_METHODS[self.replacement_method]

    @property
    def description(self):
        description = (
            'On {colname}, '
            + 'for missing values, {replacement_method}'
        ).format(
            colname=self.colname,
            replacement_method=self.replacement_method.value
        )

        return description


class TypeConversionStep(DataCleanStepBase):
    """A step to handle mistyped values in a dataframe column"""

    def __init__(self, **params):
        super(TypeConversionStep, self).__init__(**params)
        self.colname = self.params['colname']
        self.data_type = self.params['data_type']
        self.replacement_method = self.params.pop('replacement_method')

    @property
    def cleaning_function(self):
        return TYPE_CONVERT_METHODS[self.replacement_method]

    @property
    def description(self):
        description = (
            'On {colname}, '
            + 'for non {data_type} types, {replacement_method}'
        ).format(
            colname=self.colname,
            replacement_method=self.replacement_method.value,
            data_type=self.data_type.__name__
        )

        return description


class RbmStep(DataCleanStepBase):
    """A step to fill missing values with a Restricted Boltzmann Machine"""

    def __init__(self, **params):
        super(RbmStep, self).__init__(**params)
        self.numerical_columns = self.params['numerical_columns']
        self.categorical_columns = self.params['categorical_columns']

    @property
    def cleaning_function(self):
        return boltzmannclean.clean

    def execute(self, dataframe, preview=True):
        return self.cleaning_function(
            dataframe.copy() if preview else dataframe,
            tune_rbm=not preview,
            **self.params
        )

    @property
    def description(self):
        description = (
            'On {num_cols} columns, '
            + 'impute values, with an RBM'
        ).format(
            num_cols=len(self.numerical_columns + self.categorical_columns)
        )

        return description

    def render_code(self):
        return codegen.render_code(
            function=self.cleaning_function,
            tune_rbm=True,
            code_comment=self.description,
            **self.params
        )


class Pipeline(object):
    """Keeps track of which cleaning step the user wishes to apply."""

    def __init__(self):
        self.steps = []

    def append(self, step):
        self.steps.append(step)

    def remove(self, step):
        self.steps.remove(step)

    def replace(self, old_step, new_step):
        if old_step in self.steps:
            index = self.steps.index(old_step)
            self.steps.remove(old_step)
            self.steps.insert(index, new_step)

    def execute(self, dataframe, up_to_step=None, preview=True):
        """Executes the current pipeline up to up_to_step on dataframe"""

        new_dataframe = dataframe

        for step in self.steps:
            if step is up_to_step:
                break
            new_dataframe = step.execute(new_dataframe, preview)
            # avoids the unnecessary pandas SettingWithCopy warning
            new_dataframe.is_copy = False

        return new_dataframe

    def export(self):
        """Returns the python code making up the pipeline"""

        code = ''
        imports = []

        for step in self.steps:
            code += step.render_code()
            imports += step.required_import_statements()

        export_code = codegen.EXPORT_FUNCTION_SIGNATURE

        for import_statement in sorted(set(imports)):
            export_code += import_statement

        export_code += (
            codegen.STEP_CODE_PREFIX
            + code
            + codegen.STEP_CODE_SUFFIX
        )

        return export_code
