define(["require", "jquery", "base/js/namespace", 'services/config',
    'base/js/events', 'base/js/utils', 'notebook/js/codecell', 'notebook/js/outputarea'
], function(require, $, Jupyter, configmod, events, utils, codecell, outputarea) {

    var Notebook = require('notebook/js/notebook').Notebook;
    "use strict";
    var mod_name = "dataclean";
    var log_prefix = '[' + mod_name + '] ';

    var n_dataframes = 0

    // ...........Parameters configuration......................
    // define default values for config parameters if they were not present in general settings (notebook.json)
    var cfg = {
    	'position' : {
    		top: '50px'
    	},
        'window_display': false,
        'python': {
            varRefreshCmd: (`try:
                print(_datacleaner.dataframe_metadata())
            except:
                print([])`)
        .replace(/^            /gm, '')
        },
    };

    //.....................global variables....


    var st = {};
    st.config_loaded = false;
    st.extension_initialized = false;

    function read_config(cfg, callback) { // read after nb is loaded
        // create config object to load parameters
        var config = Jupyter.notebook.config;
        config.loaded.then(function() {

            cfg = $.extend(true, cfg, config.data.datacleaner);
            // then update cfg with some vars found in current notebook metadata
            // and save in nb metadata (then can be modified per document)

            // window_display is taken from notebook metadata
            if (Jupyter.notebook.metadata.datacleaner) {
                if (Jupyter.notebook.metadata.datacleaner.window_display)
                    cfg.window_display = Jupyter.notebook.metadata.datacleaner.window_display;
               	if (Jupyter.notebook.metadata.datacleaner.position)
                    cfg.position = Jupyter.notebook.metadata.datacleaner.position;
            }

            cfg = Jupyter.notebook.metadata.datacleaner = $.extend(true,
            cfg, Jupyter.notebook.metadata.datacleaner);

            // but cols and kernels_config are taken from system (if defined)
            if (config.data.datacleaner) {
                if (config.data.datacleaner.kernels_config) {
                    cfg.kernels_config = $.extend(true, cfg.kernels_config, config.data.datacleaner.kernels_config);
                }
            }

            // call callbacks
            callback && callback();
            st.config_loaded = true;
        });
        config.load();
        return cfg;
    }

    function toggledatacleaner() {
        toggle_datacleaner(cfg, st);
    }

    var datacleaner_button = function() {
        if (!Jupyter.toolbar) {
            events.on("app_initialized.NotebookApp", datacleaner_button);
            return;
        }
        if ($("#datacleaner_button").length === 0) {
            Jupyter.toolbar.add_buttons_group([{
                'label': 'Data Cleaner',
                'icon': 'fa-bar-chart-o',
                'callback': toggledatacleaner,
                'id': 'datacleaner_button'
            }]);
        }

        require(['nbextensions/sherlockml-dataclean/iosbadge'],
        function() {
            if ($("#datacleaner_button").find('.iosb').length === 0) {
                $("#datacleaner_button").iosbadge({ theme: 'grey', size: 20 });
            }
            $("#datacleaner_button").find('.iosb').addClass('hidden');
        });
    };

    var load_css = function() {
        var link = document.createElement("link");
        link.type = "text/css";
        link.rel = "stylesheet";
        link.href = require.toUrl("./main.css");
        document.getElementsByTagName("head")[0].appendChild(link);
    };


    function html_table(jsonDataframes) {
        var dfList = JSON.parse(String(jsonDataframes));
        var table = '<div class="inspector">'
            +'<table class="'
                +'tablesorter tablesorter-default table '
                +'fixed table-condensed table-nonfluid ">'
            +'<col /><col  /><col /><thead><tr>'
            +'<th >Name</th><th >Shape</th><th >Columns</th>'
            +'</tr></thead>';
        n_dataframes = dfList.length;

        for (var i = 0; i < n_dataframes; i++) {
            table +=
                '<tr class="tablesorter-hasChildRow">'
                +'<td><a href="#" class="toggleDataframe arrow-right" '
                +'data-frame-id="' + dfList[i].dfId + '">'
                + dfList[i].dfName + '</a></td><td>'
                + dfList[i].dfShape + '</td><td>'
                + dfList[i].dfColnames + '</td></tr>'
                + '<tr class=tablesorter-childRow>'
                + '<td colspan="3" class="'

                //remember if pipeline widget was hidden or shown
                if ($('#' + dfList[i].dfId + '_row').attr('class') === undefined){
                    table += 'pipeline_widget hidden';
                } else {
                    table += $('#' + dfList[i].dfId + '_row').attr('class');
                }

            table += '" id="' + dfList[i].dfId + '_row">'
                + 'Loading widget...</td></tr>'
                +'<tr class="tablesorter-childRow">'
                + '<td colspan="3" class="'

                //remember if sub-table was hidden or shown
                if ($('#table_' + dfList[i].dfId).attr('class') === undefined){
                    table += 'hidden';
                } else {
                    table += $('#table_' + dfList[i].dfId).attr('class');
                }

            table += '" id="table_' + dfList[i].dfId + '">'
                +'<table class="tablesorter'
                + '" width="100%" id="' + dfList[i].dfId + '">'
                +'<thead class="sorter-false"><tr>'
                + '<th>Column</th>'
                + '<th>Pandas dtype</th>'
                + '<th>Nulls</th>'
                + '<th># Distinct</th>'
                +'</tr></thead>'
                +'<tbody>';
            var n_cols = dfList[i].dfCols.length;
            for (var j = 0; j < n_cols; j++) {
                col = dfList[i].dfCols[j];
                table +=
                    '<tr class="tablesorter-hasChildRow">'
                    +'<td class="childColumn"><a href="#" class="toggleColumn arrow-right" '
                    +'data-frame-id="' + dfList[i].dfId +'" '
                    +'id="' + col.colId + '">'
                    + col.colname + '</a></td><td>'
                    + col.description.dtype + '</td><td>'
                    + col.description.null_percentage + '</td><td>'
                    + col.description.distinct + '</td><td>'
                    + '<tr class="tablesorter-childRow"><td colspan="4"'
                    + 'id="' + col.colId + '_row" class="';

                //remember if colwidget was hidden or shown
                if ($('#'+col.colId+'_row').attr('class') === undefined){
                    table += 'hidden';
                } else {
                    table += $('#'+col.colId+"_row").attr('class');
                }

                table += '">Loading widget...</td></tr>';
            }
            table +=
                '</tbody>'
                +'</table>'
                +'</td></tr>';
        }
        var full_table = table + '</table></div>';

        return full_table;
    }

    function display_widgets(msg, output_wrapper) {

        if (msg.header.msg_type == 'display_data') {

            var output_area = new outputarea.OutputArea({
                config: Jupyter.notebook.config,
                selector: output_wrapper,
                prompt_area: false,
                events: Jupyter.notebook.events,
                keyboard_manager: Jupyter.notebook.keyboard_manager,
            });

            output_area.handle_output(msg);
        }

        if (msg.header.msg_type == 'error') {
            console.warn(log_prefix + msg.content.evalue);
            console.warn(log_prefix + msg.content.traceback);
        }
    }

    function display_column_widget(selector) {
        if($('#datacleaner-wrapper').is(':visible')){

            var dataframe_id = $(selector).attr('data-frame-id');

            var column_id = $(selector).attr('id');

            var col_output_wrapper;

            if ($('#'+column_id+'_widget').find('.output').length===0){
                col_output_wrapper = $('<div id="'+column_id+'_widget"></div>');
                $('#'+column_id+'_row').html(col_output_wrapper);

                Jupyter.notebook.kernel.execute('_datacleaner.dataframe_managers['+dataframe_id+'].column_widget('+column_id+')',
                {iopub: { output: function(msg){display_widgets(msg, col_output_wrapper)} } }, { silent: false });
            }
        }

    }

    function display_pipeline_widget(selector) {
        if($('#datacleaner-wrapper').is(':visible')){

            var dataframe_id = $(selector).attr('data-frame-id');

            var pipeline_output_wrapper;

            if ($('#'+dataframe_id+'_widget').find('.output').length===0){
                pipeline_output_wrapper = $('<div id="'+dataframe_id+'_widget"></div>');

                $('#'+dataframe_id+'_row').html(pipeline_output_wrapper);

                Jupyter.notebook.kernel.execute('_datacleaner.dataframe_managers['+dataframe_id+'].dataframe_widget',
                    {iopub: { output: function(msg){display_widgets(msg,pipeline_output_wrapper)} } }, { silent: false });
            }
        }
    }

    //runs after every code cell execution in case dataframes have been updated
    function code_exec_callback(msg) {
        if (msg.header.msg_type == 'stream') {
            var jsonDataframes = msg.content.text;
            if (jsonDataframes === undefined)
                datacleaner_init();
            else {
            	//redraw table
                $('#datacleaner').html(html_table(jsonDataframes));

                if (n_dataframes > 0) {
                    $("#datacleaner_button").iosbadge({content: n_dataframes});
                    $("#datacleaner_button").find('.iosb').removeClass('hidden');
                } else {
                    $("#datacleaner_button").find('.iosb').addClass('hidden');
                }

           		//add click events
                $('.tablesorter').delegate('.toggleColumn', 'click' ,function(){
                    $(this).closest('tr').nextUntil('tr:not(.tablesorter-childRow)').children('td').toggleClass('hidden');
                    $(this).toggleClass('arrow-right');
                    $(this).toggleClass('arrow-down');
                    display_column_widget(this);
                    return false;
                });

                $('.tablesorter').on('click', '.toggleDataframe' ,function(){
                    $(this).closest('tr').nextUntil('tr:not(.tablesorter-childRow)').children('td').toggleClass('hidden');
                    $(this).toggleClass('arrow-right');
                    $(this).toggleClass('arrow-down');
                    display_pipeline_widget(this)
                    return false;
                });

                //redisplay already open widgets
                $('.toggleColumn').each(function(){
                    if (!($(this).closest('tr').nextUntil('tr:not(.tablesorter-childRow)').children('td').hasClass('hidden'))){
                        $(this).toggleClass('arrow-right');
                        $(this).toggleClass('arrow-down');
                        display_column_widget(this)
                    }
                });

                $('.toggleDataframe').each(function(){
                    if (!($(this).closest('tr').next('tr').find('.pipeline_widget').hasClass('hidden'))){
                        $(this).toggleClass('arrow-right');
                        $(this).toggleClass('arrow-down');
                        display_pipeline_widget(this)
                    }
                });

            }
            require(['nbextensions/sherlockml-dataclean/jquery.tablesorter.min'],
            function() {
                setTimeout(function() { if ($('#datacleaner').length>0)
                $('#datacleaner table').tablesorter()}, 100);
            });
        }

        if (msg.header.msg_type == 'error') {
            console.warn(log_prefix + msg.content.evalue);
            console.warn(log_prefix + msg.content.traceback);
        }
    }

    var varRefresh = function() {
        require(['nbextensions/sherlockml-dataclean/jquery.tablesorter.min'],
            function() {
                Jupyter.notebook.kernel.execute(
                    cfg.python.varRefreshCmd, { iopub: { output: code_exec_callback } }, { silent: false }
                );
            });
    };


    var datacleaner_init = function() {

        cfg = read_config(cfg, function() {
            if (typeof Jupyter.notebook.kernel !== "undefined" && Jupyter.notebook.kernel !== null) {
                datacleaner_button();
            } else {
                console.warn(log_prefix + "Kernel not available?");
            }
        });

        data_cleaner(cfg, st);

        //CREATE DATACLEANER PYTHON OBJECT
        Jupyter.notebook.kernel.execute((
            `try:
                _datacleaner
            except NameError:
                from dataclean.manager import DataCleaner as _DataCleaner
                _datacleaner = _DataCleaner()`)
        .replace(/^            /gm, ''))

        events.on('execute.CodeCell', varRefresh);
        events.on('varRefresh', varRefresh);
    };


    var create_datacleaner_div = function(cfg, st) {
        function save_position(){
            Jupyter.notebook.metadata.datacleaner.position = {
                'left': $('#datacleaner-wrapper').css('left'),
                'top': $('#datacleaner-wrapper').css('top'),
                'width': $('#datacleaner-wrapper').css('width'),
                'height': $('#datacleaner-wrapper').css('height'),
                'right': $('#datacleaner-wrapper').css('right')
            };
        }
        var datacleaner_wrapper = $('<div id="datacleaner-wrapper"/>')
            .append(
                $('<div id="datacleaner-header"/>')
                .addClass("header")
                .text("Data Cleaner ")
                .append(
                    $("<a/>")
                    .attr("href", "#")
                    .text("[x]")
                    .addClass("kill-btn")
                    .attr('title', 'Close window')
                    .click(function() {
                    	save_position();
                        toggledatacleaner();
                        return false;
                    })
                )
                .append(
                    $("<a/>")
                    .attr("href", "#")
                    .addClass("hide-btn")
                    .attr('title', 'Hide Data Cleaner')
                    .text("[-]")
                    .click(function() {
                        $('#datacleaner-wrapper').css('position', 'fixed');
                        $('#datacleaner').slideToggle({
                            'complete': function() {
                                    Jupyter.notebook.metadata.datacleaner['datacleaner_section_display'] = $('#datacleaner').css('display');
                                    save_position();
                                    Jupyter.notebook.set_dirty();
                            }
                        });
                        $('#datacleaner-wrapper').toggleClass('closed');
                        if ($('#datacleaner-wrapper').hasClass('closed')) {
                            cfg.oldHeight = $('#datacleaner-wrapper').height(); //.css('height');
                            $('#datacleaner-wrapper').css({ height: 40 });
                            $('#datacleaner-wrapper .hide-btn')
                                .text('[+]')
                                .attr('title', 'Show Data Cleaner');
                        } else {
                            $('#datacleaner-wrapper').height(cfg.oldHeight); //css({ height: cfg.oldHeight });
                            $('#datacleaner').height(cfg.oldHeight - $('#datacleaner-header').height() - 30 )
                            $('#datacleaner-wrapper .hide-btn')
                                .text('[-]')
                                .attr('title', 'Hide Data Cleaner');
                        }
                        return false;
                    })
                ).append(
                    $("<a/>")
                    .attr("href", "#")
                    .text("  \u21BB")
                    .addClass("reload-btn")
                    .attr('title', 'Reload Data Cleaner')
                    .click(function() {
                        varRefresh();
                        return false;
                    })
                ).append(
                    $("<span/>")
                    .html("&nbsp;&nbsp")
                ).append(
                    $("<span/>")
                    .html("&nbsp;&nbsp;")
                )
            ).append(
                $("<div/>").attr("id", "datacleaner").addClass('datacleaner')
            )

        $("body").append(datacleaner_wrapper);
        // Ensure position is fixed
        $('#datacleaner-wrapper').css('position', 'fixed');

        // enable dragging and save position on stop moving
        $('#datacleaner-wrapper').draggable({
            handle:'#datacleaner-header',
            drag: function(event, ui) {}, //end of drag function
            start: function(event, ui) {
                $(this).width($(this).width());
            },
            stop: function(event, ui) { // on save, store window position
                $(this).offset({top:Math.max($(this).offset().top,0)});
                save_position();
                Jupyter.notebook.set_dirty();
                // Ensure position is fixed (again)
                $('#datacleaner-wrapper').css('position', 'fixed');
            },
        });

        $('#datacleaner-wrapper').resizable({
            resize: function(event, ui) {
                $('#datacleaner').height($('#datacleaner-wrapper').height() - $('#datacleaner-header').height());
            },
            start: function(event, ui) {
                $(this).css('position', 'fixed');
            },
            stop: function(event, ui) {
                    save_position();
                    $('#datacleaner').height($('#datacleaner-wrapper').height() - $('#datacleaner-header').height())
                    Jupyter.notebook.set_dirty();
            }
        })

        if (Jupyter.notebook.metadata.datacleaner !== undefined) {
            if (Jupyter.notebook.metadata.datacleaner.position !== undefined) {
                $('#datacleaner-wrapper').css(Jupyter.notebook.metadata.datacleaner.position);
            }
        }

        // Ensure position is fixed
        $('#datacleaner-wrapper').css('position', 'fixed');

        // Restore window display
            if (Jupyter.notebook.metadata.datacleaner !== undefined) {
                if (Jupyter.notebook.metadata.datacleaner['datacleaner_section_display'] !== undefined) {
                    $('#datacleaner').css('display', Jupyter.notebook.metadata.datacleaner['datacleaner_section_display'])
                    if (Jupyter.notebook.metadata.datacleaner['datacleaner_section_display'] == 'none') {
                        $('#datacleaner-wrapper').addClass('closed');
                        $('#datacleaner-wrapper').css({ height: 40 });
                        $('#datacleaner-wrapper .hide-btn')
                            .text('[+]')
                            .attr('title', 'Show Data Cleaner');
                    }
                }
                if (Jupyter.notebook.metadata.datacleaner['window_display'] !== undefined) {
                    console.log(log_prefix + "Restoring Data Cleaner window");
                    $('#datacleaner-wrapper').css('display','none');
                    if ($('#datacleaner-wrapper').hasClass('closed')){
                        $('#datacleaner').height(cfg.oldHeight - $('#datacleaner-header').height())
                    }else{
                        $('#datacleaner').height($('#datacleaner-wrapper').height() - $('#datacleaner-header').height()-30)
                    }

                }
            } else {
                $('#datacleaner-wrapper').toggle();
            }

        if ($('#datacleaner-wrapper').css('display') == undefined) $('#datacleaner-wrapper').css('display', "none") //block

        datacleaner_wrapper.addClass('datacleaner-float-wrapper');

    }

    var data_cleaner = function(cfg, st) {
        var datacleaner_wrapper = $("#datacleaner-wrapper");
        if (datacleaner_wrapper.length === 0) {
            create_datacleaner_div(cfg, st);
        }

        $(window).resize(function() {
            $('#datacleaner').css({ maxHeight: $(window).height() - 30 });
            $('#datacleaner-wrapper').css({ maxHeight: $(window).height() - 10 });
        });

        $(window).trigger('resize');
        varRefresh();
    };

    var toggle_datacleaner = function(cfg, st) {
        // toggle draw (first because of first-click behavior)
        $("#datacleaner-wrapper").toggle({
            'progress': function() {},
            'complete': function() {
                    Jupyter.notebook.metadata.datacleaner['window_display'] = $('#datacleaner-wrapper').css('display') == 'block';
                    Jupyter.notebook.set_dirty();
                // recompute:
                data_cleaner(cfg, st);
            }
        });
    };


    var load_jupyter_extension = function() {
        load_css();
        datacleaner_button();

        // If a kernel is available,
        if (typeof Jupyter.notebook.kernel !== "undefined" && Jupyter.notebook.kernel !== null) {
            datacleaner_init();
        }

        events.on("kernel_ready.Kernel", function(evt, data) {
            datacleaner_init();
        });

    };

    return {
        load_ipython_extension: load_jupyter_extension,
        varRefresh: varRefresh
    };

});

/*
This code based on jupyter-varInpsector https://github.com/jfbercher/jupyter_varInspector
Now part of https://github.com/ipython-contrib/jupyter_contrib_nbextensions
which is licensed as follows:

IPython-contrib is licensed under the terms of the Modified BSD License (also known as New or Revised or 3-Clause BSD), as follows:

    Copyright (c) 2013-2015, IPython-contrib Developers

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

Neither the name of the IPython-contrib Developers nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

*/
