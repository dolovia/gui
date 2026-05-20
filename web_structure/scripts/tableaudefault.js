function changesrc(newSrc) {
	window.event.srcElement.src = newSrc;
}

  /*
   * Scripts de gestion des spans de sur-impression
   */
  //Scripts du span 'esclave'
  // fonction de développement
  function etendSpan(monSpan) {
  	monSpan.style.position = "absolute";
  	// Déplacer le calcul pour contournement d'un bug de Firefox si version < 1.5
  	// mettre une ligne au dessus pour Mozilla < 1.5
  	var realWidth = parseInt(monSpan.clientWidth); 
  	
  	// Astuce de contournement d'un bug de IE
	if (realWidth ==0) realWidth = parseInt(monSpan.clientWidth); 
	
	monSpan.style.zIndex = "+5";
	monSpan.style.backgroundColor = coulSurlignage;
	monSpan.style.color = coulTexteSurlignage;
	monSpan.style.height = monSpan.parentNode.clientHeight + "px";
	
  	if (realWidth > parseInt(monSpan.parentNode.style.width)) {
  		monSpan.style.width = realWidth+5;
		if (monSpan.getAttribute("calage") == "droite") {
			monSpan.style.right = "0px";
		} else {
			monSpan.style.left = "0px";
		}
	}
	else {
		monSpan.style.width = monSpan.parentNode.style.width;
	}
	
  }
  
  // fonction de retour à l'état initial
  function raccourciSpan(monSpan) {
  	monSpan.style.position = "relative";
  	monSpan.style.zIndex = "+1";
	monSpan.style.backgroundColor = "";
	monSpan.style.color = "";
  }
  
  // Scripts du span 'maitre'
  // fonction de développement
  function debrideSpan(monSpan) {
  	monSpan.className = "maitreEtendu";
  }

  // fonction de retour à l'état initial
  function brideSpan(monSpan) {
  	monSpan.className = "maitre";
  }
  
  // Gestion des évènement de déclenchement du déroulement des spans
  // Développement
  // onmouseover ==> cas INTERNET EXPLORER
  document.onmouseover = function() {
  	if (window.event==null) return; //cas FireFox
    var elem = window.event.srcElement;
	if (elem.getAttribute("type") == "maitre") {
		debrideSpan(elem);
		etendSpan(elem.firstChild);
	} else if (elem.getAttribute("type") == "esclave") {
		debrideSpan(elem.parentNode);
		etendSpan(elem);
	}
  }
  // onmouseover ==> cas MOZILLA FIREFOX
  if (document.addEventListener) document.addEventListener('mouseover', fmouseover, true);
  function fmouseover(evt) {
    var elem = evt.target;
    if (elem==null) return; // blindage pour firefox
	if (elem.getAttribute("type") == "maitre") {
		debrideSpan(elem);
		etendSpan(elem.firstChild);
	} else if (elem.getAttribute("type") == "esclave") {
		debrideSpan(elem.parentNode);
		etendSpan(elem);
	}
  }

  // Retour à l'état initial
  // onmouseout ==> cas INTERNET EXPLORER
  document.onmouseout = function() {
  	if (window.event==null) return; //cas FireFox
    var elem = window.event.srcElement;
	if (elem.getAttribute("type") == "maitre") {
		brideSpan(elem);
		raccourciSpan(elem.firstChild);
	} else if (elem.getAttribute("type") == "esclave") {
		brideSpan(elem.parentNode);
		raccourciSpan(elem);
	}
  }
  // Retour à l'état initial
  // onmouseout ==> cas MOZILLA FIREFOX
  if (document.addEventListener) document.addEventListener('mouseout', fmouseout, true);
  function fmouseout(evt) {
    var elem = evt.target;
    if (elem==null) return; // blindage pour firefox
	if (elem.getAttribute("type") == "maitre") {
		brideSpan(elem);
		raccourciSpan(elem.firstChild);
	} else if (elem.getAttribute("type") == "esclave") {
		brideSpan(elem.parentNode);
		raccourciSpan(elem);
	}
  }

// Fonction tout selectionner/deselectionner
function toutSelectionner(tagId) {
  // Recuperation du tag actif
  var tag = document.images[tagId];

  // Determination du sens de l'action de checking
  toSelect = (tag.getAttribute("allSelected") == "false");


  // Recuperation du formulaire du tableau
  var f = getFormTableau();
  // Recuperation des elements
  var elems = f.elements;
  // Bouclage sur les elements
  for (i=0;i<elems.length;i++) {
    el = elems[i];

    // Verification que l'element en cours est une checkbox du tableau
    if ((el.type) && (el.type == "checkbox") && (el.value == "1")) {
    	el.checked = toSelect;
    }
  }
  
  // Changement de l'etat du Tag
  tag.setAttribute("src", (toSelect ? tag.getAttribute("toutDeselectUrl"):tag.getAttribute("toutSelectUrl")));
  tag.setAttribute("allSelected", toSelect+"");

}


/**
 * Fonction d'ouverture de la popup d'aide
 */
 function ouvreInfoFiltre() {
 	newPopupCentree("./html/infoTableau.html",375,400); 
 }
 