var popup=null;
var presencePopup=false;

window.onfocus = fpresencePopup;
document.onclick = fpresencePopup;

//centrage de la popup 
//en fonction de sa largeur et de sa hauteur calcul de sa position left et top
function newPopupCentree(url,WIDTH,HEIGHT) { 
	LEFT = (screen.width)?(screen.width-WIDTH)/2:100;
	TOP = (screen.height)?(screen.height-HEIGHT)/2:100;
	newPopup(url,WIDTH,HEIGHT,LEFT,TOP);	
}

//fonction de base : tous les params sont explicites
function newPopup(url,WIDTH,HEIGHT,LEFT,TOP) { //avec 4 arguments
	arguments = "toolbar=0,location=0,directories=0,status=0,menubar=0,scrollbars=0,resizable=0";
	arguments = arguments +",width="+WIDTH+",height="+HEIGHT+",left="+LEFT+",top="+TOP;

	popup=window.open(url,'popup',arguments);
	presencePopup=true;
	popup.self.focus();	
}

function fpresencePopup(evt){
	if (!evt) { // cas Internet Explorer
		evt = window.event;
		eltclique = evt.srcElement;
	}
	else {  // cas Mozilla	
		if (evt.target) eltclique = evt.target;
	} 
	var faire_kill= true;
	if (eltclique && eltclique.getAttribute) 
	{  	
		if (eltclique !=null)
		{
			if (eltclique.getAttribute("estEltMenu") &&
		        eltclique.getAttribute("estEltMenu").length >= 0)
			{			
				// on est dans un element de menu : pas de kill
				faire_kill = false;			
			}
			else if (eltclique.parentNode &&
		  			 eltclique.parentNode != null &&
		  			 eltclique.parentNode.getAttribute &&
					 eltclique.parentNode.getAttribute("estEltMenu") &&
		        	 eltclique.parentNode.getAttribute("estEltMenu").length >= 0)
			{			
				// on est dans un element de menu : pas de kill
				faire_kill = false;			
			}			
	  	}
	}
	if (faire_kill) {
		kill();
	}
	if (presencePopup){
		//popup.open('','popup');
		popup.focus();
	}
}

