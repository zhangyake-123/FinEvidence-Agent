var $jq = jQuery.noConflict();

$jq(document).ready(function() {
    // check for document state

    if ($jq("#statementsAnchor").is(":visible")) {
        jkmegamenu.definemenu("statementsAnchor", "statementsMenu", "click");
    }

    if ($jq("#disclosuresAnchor").is(":visible")) {
        jkmegamenu.definemenu("disclosuresAnchor", "disclosuresMenu", "click");
    }

    if ($jq("#policiesAnchor").is(":visible")) {
        jkmegamenu.definemenu("policiesAnchor", "policiesMenu", "click");
    }

    if ($jq("#disclosuresTablesAnchor").is(":visible")) {
        jkmegamenu.definemenu("disclosuresTablesAnchor", "disclosuresTablesMenu", "click");
    }

    if ($jq("#disclosuresDetailsAnchor").is(":visible")) {
        jkmegamenu.definemenu("disclosuresDetailsAnchor", "disclosuresDetailsMenu", "click");
    }

    if ($jq("#documentsAnchor").is(":visible")) {
        jkmegamenu.definemenu("documentsAnchor", "documentsMenu", "click");
    }

    if ($jq("#seriesAnchor").is(":visible")) {
        jkmegamenu.definemenu("seriesAnchor", "seriesMenu", "click");
    }

    if ($jq("#schAnchor").is(":visible")) {
        jkmegamenu.definemenu("schAnchor", "schedulesMenu", "click");
    }

    if ($jq("#rptAnchor").is(":visible")) {
        jkmegamenu.definemenu("rptAnchor", "reportsMenu", "click");
    }
	
    if ($jq("#otherAnchor").is(":visible")) {
        jkmegamenu.definemenu("otherAnchor", "othersMenu", "click");
    }
	
    if ($jq("#uncategorizedAnchor").is(":visible")) {
        jkmegamenu.definemenu("uncategorizedAnchor", "uncategorizedMenu", "click");
    }
	

    $jq(function() {
        //all hover and click logic for buttons
        $jq(".eol-button:not(.ui-state-disabled)")
		    .hover(
			    function() {
			        $jq(this).addClass("ui-state-hover");
			    },
			    function() {
			        $jq(this).removeClass("ui-state-hover");
			    }
		    )
		    .mousedown(function() {
		        $jq(this).parents('.eol-buttonset-single:first').find(".eol-button.ui-state-active").removeClass("ui-state-active");
		        if ($jq(this).is('.ui-state-active.eol-button-toggleable, .eol-buttonset-multi .ui-state-active')) { $jq(this).removeClass("ui-state-active"); }
		        else { $jq(this).addClass("ui-state-active"); }
		    })
		    .mouseup(function() {
		        if (!$jq(this).is('.eol-button-toggleable, .eol-buttonset-single .eol-button,  .eol-buttonset-multi .eol-button')) {
		            $jq(this).removeClass("ui-state-active");
		        }
		    });
    });

    $jq(function() {
        //all hover and click logic for buttons
        $jq(".eol-menu-button:not(.ui-state-disabled)")
		    .hover(
			    function() {
			        $jq(this).addClass("ui-state-hover");
			    },
			    function() {
			        $jq(this).removeClass("ui-state-hover");
			    }
		    )

			//remove fixed width from SEC static stmt html files
			$jq(".stmt .report th.tl div").css("width", "");
			//console.info($jq(".stmt .report th.tl div"));
    });

//	$jq(function() {
		   function loadReport(reportID, sid) {
				var $reportShow = $jq(reportID);
				
				if(sAPIBaseURL.length > 0 && $reportShow.html().length<=0){
					$jq("#loading").removeClass("subcontainerNotSelected");
					$jq("#loading").addClass("subcontainerSelected");
					if(sid){
						$jq.ajax({
							type: "GET",
							url: sAPIBaseURL + sid,
							cache: true,
							dataType: "text",
							success: function (data) { 
									var startInd=data.indexOf("<body>");
									var endInd=data.indexOf("</body>");
									if(startInd>0) {startInd=startInd+6;}
									else {startInd=0;}
									if(endInd<=startInd) {endInd=data.length;}
									$reportShow.append(data.substring(startInd, endInd))
								},
							error: function(){
								$jq("#error").removeClass("subcontainerNotSelected");
								$jq("#error").addClass("subcontainerSelected");
							},
							complete: function(){
									$jq("#loading").removeClass("subcontainerSelected");
									$jq("#loading").addClass("subcontainerNotSelected");
							}
						});
					}
				}				
		   }
//	});
	
    $jq(".reportLink").bind("click",
        function() {
            // Change the current link to bold
            // and the previously selected link if there is one to not bold.
            $jq(".linkBold").removeClass("linkBold");
            $jq(this).addClass("linkBold");

            // Find the report of the link and make it visible.
            // Find the report of the old link and make it not visible.
            var $bar = "#" + $jq(this).attr("reportID");
            var $reportShow = $jq($bar);

            $jq(".reportContainer").removeClass("subcontainerSelected");
            $jq(".reportContainer").addClass("subcontainerNotSelected");

			$reportShow.removeClass("subcontainerNotSelected");
			
			// do animation to load the report
			if(doAnimateReport) {
				$reportShow.addClass("show");
				setTimeout(function(){
				  $reportShow.removeClass("show");
				  $reportShow.addClass("subcontainerSelected");
				},320); // timed to occur immediately
			}
			else {
				$reportShow.addClass("subcontainerSelected");
			}

			if(sAPIBaseURL.length > 0 && $reportShow.html().length<=0){
				$jq("#loading").removeClass("subcontainerNotSelected");
				$jq("#loading").addClass("subcontainerSelected");
				var sid =  $jq(this).attr("sectionID")
				if(sid){
					var apiURL = sAPIBaseURL + sid;
				    $jq.ajax({
						type: "GET",
						url: apiURL,
						cache: true,
						dataType: "text",
						//async:false,
						success: function (data) { 
								var startInd=data.indexOf("<body>");
								var endInd=data.indexOf("</body>");
								if(startInd>0) {startInd=startInd+6;}
								else {startInd=0;}
								if(endInd<=startInd) {endInd=data.length;}
								$reportShow.append(data.substring(startInd, endInd))
							},
						error: function(){
							$jq("#error").removeClass("subcontainerNotSelected");
							$jq("#error").addClass("subcontainerSelected");
						},
						complete: function(){
								$jq("#loading").removeClass("subcontainerSelected");
								$jq("#loading").addClass("subcontainerNotSelected");
						}
				    });
				}
			}
        });

		// Set the first report to be visible.
    $jq(".markFirstAsSelected").addClass("linkBold");
    var $reportShowFirstID = "#" + $jq(".markFirstAsSelected").attr("reportID");
    var $reportShowFirst = $jq($reportShowFirstID);
    $reportShowFirst.removeClass("subcontainerNotSelected");
    $reportShowFirst.addClass("subcontainerSelected");
	
	//load default report in V3
	if(defaultSID && defaultSID !=""){
		loadReport("#Report1", defaultSID);
	}
})
