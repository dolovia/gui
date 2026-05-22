var survivant="**";

// Constantes
var prefCalque="calque_";
var prefSsMenu="ssMen_";
var prefPicto="picto_";
var suffImgDroite="_versDroite.gif";
var suffImgBas="_versBas.gif";
var calcOuvert = new Array();

function kill() {
	killAsynchrone();
}


function killAsynchrone() {
    var tamponCalcOuvert = new Array();
    for (i=0;i<calcOuvert.length;i++) {
    	nomElem = calcOuvert[i];
    	if (survivant==null) survivant="**";
    	
    	if (survivant.indexOf("**"+nomElem+"**") <0) {
    	
    		elem = document.getElementById(nomElem);
    		if (nomElem.indexOf(prefCalque) == 0) {
				elem.style.visibility = 'hidden';
				codeCalque = nomElem.substring(prefCalque.length,nomElem.length);
				imgAssociee = document.getElementById(prefPicto+codeCalque);
				if (imgAssociee) {orientePicto(imgAssociee,suffImgDroite);}
    		}
    		
			if (nomElem.indexOf(prefSsMenu) == 0) {
				elem.style.visibility = 'hidden';
				elem.style.position  = 'absolute';
				codeCalque = nomElem.substring(prefSsMenu.length,nomElem.length);
				imgAssociee = document.getElementById(prefPicto+codeCalque);
				if (imgAssociee) {orientePicto(imgAssociee,suffImgDroite);}
			}
		
    	} else {    	
    		tamponCalcOuvert[tamponCalcOuvert.length]=nomElem;    	
    	}
    }
    
	calcOuvert = tamponCalcOuvert;
  	survivant="**";
}

function affCalque(nomCalque, listesurvivant) {
  var calq = eval("document.getElementById(\""+nomCalque+"\")");
  if (calq) {
    calq.style.visibility = 'visible';
    calq.style.display='block';
	codeCalque = calq.id.substring(prefCalque.length,calq.id.length);
	imgAssociee = eval("document.getElementById(\""+prefPicto+codeCalque+"\")");
	if (imgAssociee) {orientePicto(imgAssociee,suffImgBas);}
	// ajout au tableau
	calcOuvert[calcOuvert.length] = nomCalque;
	// sauvegarde
	survivant = listesurvivant;
	// on ferme les autres menus
	kill();
  }
}

function affSsMen(nomSsMenu, listesurvivant) {
  var calq = eval("document.getElementById(\""+nomSsMenu+"\")");
  if (calq) {
    calq.style.position  = 'relative';
	setTimeout("document.getElementById(\""+nomSsMenu+"\").style.visibility = 'hidden'",5);
	setTimeout("document.getElementById(\""+nomSsMenu+"\").style.visibility = 'visible'",10);
	codeCalque = calq.id.substring(prefSsMenu.length,calq.id.length);
	imgAssociee = eval("document.getElementById(\""+prefPicto+codeCalque+"\")");
	if (imgAssociee) {orientePicto(imgAssociee,suffImgBas);}
	// ajout au tableau
	calcOuvert[calcOuvert.length] = nomSsMenu;
	// sauvegarde
	survivant = listesurvivant;
	// on ferme les autres menus
	kill();
  }
}


function orientePicto(image,suffixe) {
  srcSplit = image.src.split("_");
  nouvSrc ="";
  for (j=0;j<srcSplit.length-1;j++) {
  	nouvSrc += srcSplit[j];
  	if (j < srcSplit.length-2) {
  		nouvSrc += "_"; 
  	}
  }
  nouvSrc += suffixe;
  image.src = nouvSrc;
}


function epargne(nomCalque) {
  survivant+=(nomCalque+"**");
}


// A completer par les projets
// Suggestion Sema : la fonction envoie au serveur le premier formulaire trouvé avec pour action 'act'.do
//Lorsque la fonction fait est appelée, le parametre de cette fonction est
//récupéré puis concaténé avec .do ( ex toto.do)
//Toutes les requetes de type *.do pointe vers le doStartTag() du TagSupport ( ex: ZoneMenusTag )
//cette action *.do doit être référencé dans struts-config.xml :

//Par exemple :
//Si on crée un bouton struts dans le formulaire de la jsp BookView.jsp :

//<html:form action="toto" method="POST">
//<html:button property="b" value="BOUTON" onclick="fait('toto')" /> 
//</html:form>

//Struts-config.xml doit contenir :
//Le global forwards est un nom connu par l'ensemble de l'application
//il est possible de conditionner l'action du formulaire pour lui dire
//par exemple que si une erreur survient il faut se diriger vers le forward global
//qui peut être une jsp d'erreur.
//
//<global-forwards>
//		<forward name="executer" path="/nom_jsp_destination.jsp"/>
//</global-forwards>
//
//<action-mappings>
//<action 	path="/toto"                   : correspond a toto.do
// 		type="strutsshop.totoAction"       : nom de la servlet Struts
//		name="boobook"                     : nom de l'action
//		scope="request"                    : portée de l'action, dans ce cas c'est en requete, possibilité de mettre session par exemple
//   	input="/nom_jsp_destination.jsp">  : nom de la jsp de destination
//</action>

function fait(act) {
  /*alert(act);
  if ((document.forms) && (document.forms[0])) {
    document.forms[0].action = act+".do";
    document.forms[0].submit();
  }*/
}






