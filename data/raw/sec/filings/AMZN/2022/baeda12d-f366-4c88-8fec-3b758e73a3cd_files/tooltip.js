function findParentNode(parentName, childObj) {
    var testObj = childObj.parentNode;
    while (testObj.nodeName != parentName) {
        testObj = testObj.parentNode;
    }
    return testObj;
}

var _sDataValueDelimiter = "^";

function addToolTips() {
    var thealinks = document.getElementsByTagName("div");
    if (!thealinks)
        return;

    for (var x = 0; x != thealinks.length; x++) {
        if (thealinks[x].className != "addToolTip")
            continue;

        // Create a custom html for the tooltip
        var innerDiv = thealinks[x].childNodes;
        var innerDivText = "<div class='tooltipmaintitle'>XBRL Properties</div>";

        var parent = findParentNode('TD', thealinks[x]);
        if (!parent)
            return;

        var rowParent = findParentNode('TR', parent);
        if (!rowParent)
            return;

        var rowSplits = rowParent.getAttribute('tooltiptext');
        if (rowSplits == '')
            return;

        var rowSplitsArr = rowSplits.split(_sDataValueDelimiter);

        var splits = parent.getAttribute('tooltiptext');
        var colSplitsArr = splits.split(_sDataValueDelimiter);

        var innerDivText = createCellPropertiesDialog(rowSplitsArr, colSplitsArr);

        thealinks[x].setAttribute("tooltiptext", innerDivText);
        thealinks[x].removeAttribute("title");
        thealinks[x].onmouseover = function gomouseover() { ddrivetip(this.getAttribute("tooltiptext")) };
        thealinks[x].onmouseout = function gomouseout() { hideddrivetip(); };
    }
}

// Create the label and value TDs for the cell properties dialog.
function createCellPropSingleColumnRow(sLabel, sValue) {
    var sReturn = "<tr><td class='tooltipRowLabel'>";
    sReturn += sLabel;
    sReturn += "</td><td colspan='3' class='tooltipRowValue'>";
    sReturn += sValue;
    sReturn += "</td></tr>";
    return sReturn;
}

// Create the label and value TDs for the cell properties dialog.
function createCellPropSingleCell(sLabel, sValue) {
    var sReturn = "<td class='tooltipRowLabel' width='10%'>";
    sReturn += sLabel;
    sReturn += "</td><td class='tooltipRowValue' width='40%'>";
    sReturn += sValue;
    sReturn += "</td>";
    return sReturn;
}

// Show the cell dialog.
function createCellPropertiesDialog(asRwInfo, asClmnInfo) {
    var innerDivText = "";

    innerDivText += "<div class='tooltipmaintitle'>XBRL Properties</div>";
    innerDivText += "<table cellpadding='4' cellspacing='0' border='0' class='ToolTipTable'>";

    if (asRwInfo.length > 0) {
        innerDivText += createCellPropSingleColumnRow("Label", asRwInfo[1]);
        innerDivText += createCellPropSingleColumnRow("Tag", asRwInfo[3]);

        // Check to see if we have dimension info to display.
        var sDimInfo = asClmnInfo[3];
        if (sDimInfo == null || sDimInfo.length == 0) {
            // If no dimension from the column, check for a dimension on the row.
            sDimInfo = asRwInfo[7];
        }

        if (sDimInfo != null && sDimInfo.length > 0) {
            sDimInfo = sDimInfo.replace(/=>/g, " => ");
            sDimInfo = sDimInfo.replace(/;;;/g, ";<br/>");
            innerDivText += createCellPropSingleColumnRow("Dimension", sDimInfo);
        }

        if (asClmnInfo.length > 0) {
            // rendered value
            innerDivText += "<tr>";
            innerDivText += createCellPropSingleCell("Rendered Value", asClmnInfo[2]);

            // negated label
            var sNegated = asClmnInfo[1];
            if (sNegated.length == 0)
                sNegated = "False";

            innerDivText += createCellPropSingleCell("Negated Label", sNegated)
            innerDivText += "</tr>";

            // instance value
            innerDivText += "<tr>";
            innerDivText += createCellPropSingleCell("Instance Value", asClmnInfo[6]);

            // data type
            innerDivText += createCellPropSingleCell("Data Type", asRwInfo[6]);
            innerDivText += "</tr>";

            // units
            // period
            var sPeriodData = asClmnInfo[0];

            // if the value contains a dash - it's a range
            var sPeriodLabel = (sPeriodData.indexOf('-') >= 0) ? "Period" : "Date";
            innerDivText += "<tr>"
            innerDivText += createCellPropSingleCell(sPeriodLabel, sPeriodData);

            innerDivText += createCellPropSingleCell("Units", asClmnInfo[4]);
            innerDivText += "</tr>";

            // balance
            innerDivText += "<tr>";
            innerDivText += createCellPropSingleCell("Balance", asRwInfo[2]);

            innerDivText += "<td></td></tr>";
        }
    }

    innerDivText += "</table>";

    return innerDivText;
}

var offsetfromcursorX = -7; //Customize x offset of tooltip
var offsetfromcursorY = 13; //Customize y offset of tooltip

var offsetdivfrompointerX = 13; //Customize x offset of tooltip DIV relative to pointer image
var offsetdivfrompointerY = 13; //Customize y offset of tooltip DIV relative to pointer image
//Tip: Set it to (height_of_pointer_image-1).

document.write('<div id="theToolTip"></div>'); //write out tooltip DIV
document.write('<img id="ToolTipPointer" runat="server" src="' + sToolTipArrow + '">'); //write out pointer image

var ie = document.all;
var ns6 = document.getElementById && !document.all;
var enabletip = false;

var opac = 0;

if (ie || ns6) {
    var tipobj = document.all ? document.all["theToolTip"] : document.getElementById ? document.getElementById("theToolTip") : "";
}

var pointerobj = document.all ? document.all["ToolTipPointer"] : document.getElementById ? document.getElementById("ToolTipPointer") : "";

function ietruebody() {
    return (document.compatMode && document.compatMode != "BackCompat") ? document.documentElement : document.body;
}

function ddrivetip(thetext, thewidth, thecolor) {
    if (ns6 || ie) {
        if (typeof thewidth !== "undefined") { tipobj.style.width = thewidth + "px"; }
        if (typeof thecolor !== "undefined" && thecolor !== "") { tipobj.style.backgroundColor = thecolor; }
        tipobj.innerHTML = thetext;
        enabletip = true;
        return false;
    }
}

var is_chrome = navigator.userAgent.toLowerCase().indexOf('chrome') > -1;
var is_firefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;
var is_safari = navigator.userAgent.toLowerCase().indexOf('safari') > -1;


var currentDivRequest;
var currentImageRequest;
var currentNonDefaultRequest;

function positiontip(e) {
    if (enabletip) {
        pointerobj.src = sToolTipArrow;
        pointerobj.style.filter = "";
        var nondefaultpos = false;
        var curX = (ns6) ? e.pageX : event.clientX + ietruebody().scrollLeft;
        var curY = (ns6) ? e.pageY : event.clientY + ietruebody().scrollTop - 10;
        //Find out how close the mouse is to the corner of the window
        var winwidth = ie && !window.opera ? ietruebody().clientWidth : window.innerWidth - 20;
        var winheight = ie && !window.opera ? ietruebody().clientHeight : window.innerHeight - 20;

        var rightedge = ie && !window.opera ? winwidth - event.clientX - offsetfromcursorX : winwidth - e.clientX - offsetfromcursorX;
        var bottomedge = ie && !window.opera ? winheight - event.clientY - offsetfromcursorY : winheight - e.clientY - offsetfromcursorY;

        var leftedge = (offsetfromcursorX < 0) ? offsetfromcursorX * (-1) : -1000;

        //if the HORIZONTAL distance isn't enough to accomodate the width of the context menu
        if (rightedge < tipobj.offsetWidth) {
            //move the horizontal position of the menu to the left by it's width
            tipobj.style.left = curX - (tipobj.offsetWidth - rightedge) - 10 + "px";
            nondefaultpos = true;
        }
        else if (curX < leftedge + 35) {
            tipobj.style.left = "5px";
            nondefaultpos = true;
        }
        else {
            //position the horizontal position of the menu where the mouse is positioned
            tipobj.style.left = curX + offsetfromcursorX - offsetdivfrompointerX - 30 + "px";
            pointerobj.style.left = curX + offsetfromcursorX + "px";
        }

        //same concept with the VERTICAL position
        if (bottomedge < tipobj.offsetHeight - 42 && ((winheight - bottomedge) > tipobj.offsetHeight)) {
            tipobj.style.top = curY - tipobj.offsetHeight - offsetfromcursorY + "px";
            pointerobj.src = sToolTipDownArrow;

            // Detect browsers
            if (is_chrome || is_firefox || is_safari) {
                pointerobj.style.top = curY + offsetfromcursorY + offsetdivfrompointerY - 41 + "px";
            }
            else {
                pointerobj.style.top = curY + offsetfromcursorY + offsetdivfrompointerY - 46 + "px";
            }
            // Add shadow to the pointer image
            pointerobj.style.filter = "progid:DXImageTransform.Microsoft.Shadow(color=gray,direction=135,strength=5)";
            nondefaultpos = true;
        }
        else {
            /*if(bottomedge < tipobj.offsetHeight)
            {
            window.scroll(0,tipobj.offsetHeight-bottomedge);
            scrolldelay = setTimeout('pageScroll()',120);
            clearTimeout(scrolldelay);
            }*/
            tipobj.style.top = curY + offsetfromcursorY + offsetdivfrompointerY + "px";
            pointerobj.style.top = curY + offsetfromcursorY + "px";
        }
        // create a delay
        currentRequest = setTimeout("tipobj.style.visibility='visible';", 490);

        if (!nondefaultpos) {
            currentNonDefaultRequest = setTimeout("pointerobj.style.visibility='visible';", 490);
        }

        else {
            pointerobj.style.left = curX + offsetfromcursorX - offsetdivfrompointerX + 5 + "px"; // -20
            currentImageRequest = setTimeout("pointerobj.style.visibility='visible';", 490);
        }
    }
}

function hideddrivetip() {
    if (ns6 || ie) {
        enabletip = false;

        clearTimeout(currentRequest);
        clearTimeout(currentImageRequest);
        clearTimeout(currentNonDefaultRequest);

        pointerobj.style.visibility = "hidden";
        pointerobj.style.left = "-1000px";
        tipobj.style.visibility = "hidden";
        tipobj.style.left = "-1000px";
        tipobj.style.backgroundColor = '';
        tipobj.style.width = '';
    }
}

document.onmouseover = positiontip;
addToolTips();
