// effacer.js
function effacer(a) {
	effacer_cookies();
	document.location.href='jsp/accueil/startPQ.jsp';
}

function effacer_cookies() {
	setcookie("NIR","");
	setcookie("NOM","");
	setcookie("PRENOM","");
	setcookie("DATE_NAIS","");
	setcookie("DATE_SOINS","");	
}

function setcookie(name,value) {
	var url = window.location.href.toString();
	if (url.substring(0,5) == "https")
		document.cookie = name + "=" + value+ "; path=/; secure";
	else
		document.cookie = name + "=" + value+ "; path=/";
}