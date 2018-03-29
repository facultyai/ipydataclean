sherlockml-dataclean
====================

Jupyter notebook extension and python library for interactive cleaning of pandas DataFrames with a selection of techniques, from simple replacements of missing values to imputation with a Restricted Boltzmann Machine.

Installation
------------

.. code-block:: bash

    pip install sherlockml-dataclean
    jupyter nbextension enable dataclean --py --sys-prefix

Usage
-----

Use your Jupyter notebook as normal. When a pandas DataFrame is present in your python kernel you should see a new notification on the Data Cleaner icon in your toolbar. DataFrames with names beginning with an underscore will be ignored.

.. figure:: https://user-images.githubusercontent.com/29061040/37827637-30cf156a-2e90-11e8-9b84-81a41cf94898.png
   :width: 25 %
   :alt: Data Cleaner toolbar icon.

   Data Cleaner toolbar icon.

Clicking on the icon will open a floating window containing a summary of the DataFrames in your kernel. Clicking on the name of one of these DataFrames will show some of the Data Cleaner controls and some summary statistics on the DataFrame columns.

.. figure:: https://user-images.githubusercontent.com/29061040/37827939-520b095e-2e91-11e8-8a85-a4d8cb0dfed1.png
   :width: 25 %
   :alt: Data Cleaner window.

   Data Cleaner window.

Clicking on the name of one of these columns will show data cleaning tools specific to that column, with a histogram or bar chart showing the distribution of these values. As you create a step the effect that this will have on the data distribution is shown as a preview.

.. figure:: https://user-images.githubusercontent.com/29061040/37828167-169edb9c-2e92-11e8-88cd-f918d2c498df.png
   :width: 50 %
   :alt: Creating a data cleaning step on a column.

   Creating a data cleaning step on a column.

You can also choose to fill in missing and mistyped values in your DataFrame with a Restricted Boltzmann Machine. This uses the sherlockml-boltzmannclean package.

.. figure:: https://user-images.githubusercontent.com/29061040/37828870-d096628e-2e94-11e8-9291-511fab3bdf7a.png
   :width: 40 %
   :alt: Creating a Restricted Boltzmann Machine cleaning step.

   Creating a Restricted Boltzmann Machine cleaning step.

Once you create your steps they are added to a processing pipeline which can be viewed in the "Pipeline" widget.

.. figure:: https://user-images.githubusercontent.com/29061040/37829003-4488afda-2e95-11e8-9995-9ebc1348d2bf.png
   :width: 40 %
   :alt: A data cleaning pipeline.

   A data cleaning pipeline.

These steps can be modified or deleted using these controls, and when ready the pipeline can be executed on the dataframe or output to code. Executing your pipeline will create a new DataFrame with the suffix "_cleaned" in your kernel, while exporting will create a new code cell in your notebook defining a python function which will carry out the pipeline cleaning steps.

.. figure:: https://user-images.githubusercontent.com/29061040/37829131-bf920dd4-2e95-11e8-9e77-aaa3533c2095.png
   :width: 40 %
   :alt: An exported pipeline.

   An exported pipeline.


Caveats
-------

Duplicated or non string column names are not supported.

For DataFrames over 1000 rows, a sample of 1000 rows will be used for previewing and creating your processing pipeline, with the whole DataFrame only operated on when the pipeline is executed.