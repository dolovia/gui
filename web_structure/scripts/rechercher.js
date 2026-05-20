// rechercher.js
function rechercher() {
	creationcookies();
	document.forms[0].submit();
}

function creationcookies() {
	var nni = document.forms['ConsultationForm'].elements['nni'].value;
	if (nni != null) {
		setcookie('NIR',nni);
	}
	// FS 00779657 : plus de limite (15 caracteres)
	var nom = document.forms['ConsultationForm'].elements['nom'].value;
	if (nom != null) {
		setcookie('NOM', nom);
	}
	// FS 00779657 : plus de limite (25 caracteres)
	var prenom = document.forms['ConsultationForm'].elements['prenom'].value;
	if (prenom != null) {
		setcookie('PRENOM', prenom);
	}
	var datenais = document.forms['ConsultationForm'].elements['naissance'].value;
	if (datenais != null) {
		setcookie('DATE_NAIS',datenais);
	}
	var datesoins = document.forms['ConsultationForm'].elements['datesoins'].value;
	if (datesoins != null) {
		setcookie('DATE_SOINS',datesoins);
	}
}

function setcookie(name,value) {
	var url = window.location.href.toString();
	if (url.substring(0,5) === 'https') {
		document.cookie = name + '=' + value+ '; path=/; secure';
	}
	else {
		document.cookie = name + '=' + value+ '; path=/';
	}
}
