/* jQuery Mega Menu v1.02
* Last updated: June 29th, 2009. This notice must stay intact for usage 
* Author: JavaScript Kit at http://www.javascriptkit.com/
* Visit http://www.javascriptkit.com/script/script2/jScale/ for full source code
*/

var $jkmegamenu = jQuery.noConflict();

//jQuery.noConflict();
var jkmegamenu = {

    effectduration: 300, //duration of animation, in milliseconds
    delaytimer: 1000 * 1000, //260, //delay after mouseout before menu should be hidden, in milliseconds

    //No need to edit beyond here
    megamenulabels: [],
    megamenus: [], //array to contain each block menu instances
    zIndexVal: 1000, //starting z-index value for drop down menu
    $shimobj: null,

    addshim: function($jkmegamenu) {
        $jkmegamenu(document.body).append('<IFRAME id="outlineiframeshim" src="' + (location.protocol == "https:" ? 'https://content.edgar-online.com/rxbrlviewer/html/blank.htm' : 'about:blank') + '" style="display:none; left:0; top:0; z-index:999; position:absolute; filter:progid:DXImageTransform.Microsoft.Alpha(style=0,opacity=0)" frameBorder="0" scrolling="no"></IFRAME>')
        this.$shimobj = $jkmegamenu("#outlineiframeshim")
    },

    alignmenu: function($jkmegamenu, e, megamenu_pos) {
        var megamenu = this.megamenus[megamenu_pos]
        var $anchor = megamenu.$anchorobj
        var $menu = megamenu.$menuobj
        var menuleft

        if ($jkmegamenu(window).width() - (megamenu.offsetx - $jkmegamenu(document).scrollLeft()) > megamenu.actualwidth)
            menuleft = megamenu.offsetx;
        else if (megamenu.offsetx - megamenu.actualwidth + megamenu.anchorwidth > 10)
            menuleft = megamenu.offsetx - megamenu.actualwidth + megamenu.anchorwidth;
        else
            menuleft = 10;

        //var menutop=($(window).height()-(megamenu.offsety-$(document).scrollTop()+megamenu.anchorheight)>megamenu.actualheight)? megamenu.offsety+megamenu.anchorheight : megamenu.offsety-megamenu.actualheight
        var menutop = megamenu.offsety + megamenu.anchorheight  //get y coord of menu
        $menu.css({ left: menuleft + "px", top: menutop + "px" })
        this.$shimobj.css({ width: megamenu.actualwidth + "px", height: megamenu.actualheight + "px", left: menuleft + "px", top: menutop + "px", display: "block" })
    },

    showmenu: function(e, megamenu_pos) {
        var megamenu = this.megamenus[megamenu_pos];
        var $anchor = megamenu.$anchorobj;
        //if ($anchor.css("backgroundImage") != "none" && $anchor.attr("id") != "printAnchor")
        //    $anchor.css("backgroundImage", "url(../img/arrowDown.png)");

        for (var i = 0; i < jkmegamenu.megamenus.length; i++) {
            if (jkmegamenu.megamenus[i].$menuobj.css("display") == "block") {
                this.hidemenu(e, i);
            }
        }

        // Check for bug
        $jkmegamenu('body').click(function(event) {
            if ($jkmegamenu(event.target).attr("id") != "print_comments"
                && $jkmegamenu(event.target).attr("id") != "print_tags"
                && $jkmegamenu(event.target).attr("id") != "print_defs") {
                for (var i = 0; i < jkmegamenu.megamenus.length; i++) {
                    if (jkmegamenu.megamenus[i].$menuobj.css("display") == "block") {
                        var megamenu = jkmegamenu.megamenus[i];
                        var $anchor = megamenu.$anchorobj;
                        //if ($anchor.css("backgroundImage") != "none" && $anchor.attr("id") != "printAnchor")
                        //    $anchor.css("backgroundImage", "url(../img/arrow.png)");
                        var $menu = megamenu.$menuobj;
                        var $menuinner = megamenu.$menuinner;
                        jkmegamenu.hidemenu(e, i);
                    }
                }
            }
        })

        var megamenu = this.megamenus[megamenu_pos]
        var $menu = megamenu.$menuobj
        var $menuinner = megamenu.$menuinner
        if ($menu.css("display") == "none") {
            this.alignmenu(jQuery, e, megamenu_pos)
            $menu.css("z-index", ++this.zIndexVal)
            $menu.show(this.effectduration, function() {
                $menuinner.css('visibility', 'visible')
            })
        }
        else if ($menu.css("display") == "block" && e.type == "click") { //if menu is hidden and this is a "click" event (versus "mouseout")
            this.hidemenu(e, megamenu_pos);
        }
        return false
    },

    hidemenu: function(e, megamenu_pos) {
        var megamenu = this.megamenus[megamenu_pos]

        if (megamenu) {
            var $anchor = megamenu.$anchorobj;
            //if ($anchor.css("backgroundImage") != "none" && $anchor.attr("id") != "printAnchor")
            //    $anchor.css("backgroundImage", "url(../img/arrow.png)");

            var $menu = megamenu.$menuobj
            var $menuinner = megamenu.$menuinner
            $menuinner.css('visibility', 'hidden')
            this.$shimobj.css({ display: "none", left: 0, top: 0 })
            $menu.hide(this.effectduration)
        }
    },

    definemenu: function(anchorid, menuid, revealtype) {
        this.megamenulabels.push([anchorid, menuid, revealtype])
    },

    render: function($jkmegamenu) {
        for (var i = 0, labels = this.megamenulabels[i]; i < this.megamenulabels.length; i++, labels = this.megamenulabels[i]) {
            if ($jkmegamenu('#' + labels[0]).length != 1 || $jkmegamenu('#' + labels[1]).length != 1) //if one of the two elements are NOT defined, exist
                return
            this.megamenus.push({ $anchorobj: $jkmegamenu("#" + labels[0]), $menuobj: $jkmegamenu("#" + labels[1]), $menuinner: $jkmegamenu("#" + labels[1]).children('ul:first-child'), revealtype: labels[2], hidetimer: null })
            var megamenu = this.megamenus[i]
            megamenu.$anchorobj.add(megamenu.$menuobj).attr("_megamenupos", i + "pos") //remember index of this drop down menu
            megamenu.actualwidth = megamenu.$menuobj.outerWidth()
            megamenu.actualheight = megamenu.$menuobj.outerHeight()
            megamenu.offsetx = megamenu.$anchorobj.offset().left
            megamenu.offsety = megamenu.$anchorobj.offset().top
            megamenu.anchorwidth = megamenu.$anchorobj.outerWidth()
            megamenu.anchorheight = megamenu.$anchorobj.outerHeight()
            $jkmegamenu(document.body).append(megamenu.$menuobj) //move drop down menu to end of document
            megamenu.$menuobj.css("z-index", ++this.zIndexVal).hide()
            megamenu.$menuinner.css("visibility", "hidden")
            megamenu.$anchorobj.bind(megamenu.revealtype == "click" ? "click" : "mouseenter", function(e) {
                var menuinfo = jkmegamenu.megamenus[parseInt(this.getAttribute("_megamenupos"))]
                clearTimeout(menuinfo.hidetimer) //cancel hide menu timer
                return jkmegamenu.showmenu(e, parseInt(this.getAttribute("_megamenupos")))
            })
            megamenu.$anchorobj.bind("mouseleave", function(e) { //mouseleave ************************************
                var menuinfo = jkmegamenu.megamenus[parseInt(this.getAttribute("_megamenupos"))]
                if (e.relatedTarget != menuinfo.$menuobj.get(0) && $jkmegamenu(e.relatedTarget).parents("#" + menuinfo.$menuobj.get(0).id).length == 0) { //check that mouse hasn't moved into menu object
                    menuinfo.hidetimer = setTimeout(function() { //add delay before hiding menu
                        jkmegamenu.hidemenu(e, parseInt(menuinfo.$menuobj.get(0).getAttribute("_megamenupos")))
                    }, jkmegamenu.delaytimer)
                }
            })
            megamenu.$menuobj.bind("mouseenter", function(e) {
                var menuinfo = jkmegamenu.megamenus[parseInt(this.getAttribute("_megamenupos"))]
                clearTimeout(menuinfo.hidetimer) //cancel hide menu timer
            })
            megamenu.$menuobj.bind("click mouseleave", function(e) { //mouseleave *************************************
                var menuinfo = jkmegamenu.megamenus[parseInt(this.getAttribute("_megamenupos"))]
                menuinfo.hidetimer = setTimeout(function() { //add delay before hiding menu
                    jkmegamenu.hidemenu(e, parseInt(menuinfo.$menuobj.get(0).getAttribute("_megamenupos")))
                }, jkmegamenu.delaytimer)
            })
        } //end for loop
        if (/Safari/i.test(navigator.userAgent)) { //if Safari
            $jkmegamenu(window).bind("resize load", function() {
                for (var i = 0; i < jkmegamenu.megamenus.length; i++) {
                    var megamenu = jkmegamenu.megamenus[i]
                    var $anchorisimg = (megamenu.$anchorobj.children().length == 1 && megamenu.$anchorobj.children().eq(0).is('img')) ? megamenu.$anchorobj.children().eq(0) : null
                    if ($anchorisimg) { //if anchor is an image link, get offsets and dimensions of image itself, instead of parent A
                        megamenu.offsetx = $anchorisimg.offset().left
                        megamenu.offsety = $anchorisimg.offset().top
                        megamenu.anchorwidth = $anchorisimg.width()
                        megamenu.anchorheight = $anchorisimg.height()
                    }
                }
            })
        }
        else {
            $jkmegamenu(window).bind("resize", function() {
                for (var i = 0; i < jkmegamenu.megamenus.length; i++) {
                    var megamenu = jkmegamenu.megamenus[i]
                    megamenu.offsetx = megamenu.$anchorobj.offset().left
                    megamenu.offsety = megamenu.$anchorobj.offset().top
                }
            })
        }
        jkmegamenu.addshim($jkmegamenu)
    }

}

jQuery(document).ready(function($jkmegamenu){
	jkmegamenu.render($jkmegamenu)
})
