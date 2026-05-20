function ChargePage(page) {
	document.location.href(page);
}

function chargementValeurs() {
	if (readcookie('NIR')){
		document.forms['ConsultationForm'].elements['nni'].value = readcookie('NIR');
	}
	var nom = readcookie('NOM');
	if (nom) {
		// test caractere '*' ds la chaine
		if (nom.indexOf('*') >= 0) {
			var index  = nom.indexOf('*');
			var Re = new RegExp('\\*', 'g');
			nom = nom.replace(Re, '');
			document.forms['ConsultationForm'].elements['nom'].value = nom;
			setCaretPosition(document.getElementById('idnom'),index);
		}
		else {
			document.forms['ConsultationForm'].elements['nom'].value = nom;
		}
	}
	var prenom = readcookie('PRENOM');
	if (prenom) {
		// test caractere '*' ds la chaine
		if (prenom.indexOf('*') >= 0) {
			var index  = prenom.indexOf('*');
			var Re = new RegExp('\\*', 'g');
			prenom = prenom.replace(Re, '');
			document.forms['ConsultationForm'].elements['prenom'].value = prenom;
			setCaretPosition(document.getElementById('idpre'),index);
		}
		else {
			document.forms['ConsultationForm'].elements['prenom'].value = prenom;
		}
	}
	if (readcookie('DATE_NAIS')) {
		document.forms['ConsultationForm'].elements['naissance'].value = readcookie('DATE_NAIS');
	}
	if (readcookie('DATE_SOINS')) {
		document.forms['ConsultationForm'].elements['datesoins'].value = readcookie('DATE_SOINS');
	}
}

function readcookie(name) {
	var nameEQ = name + '=';
	var ca = document.cookie.split(';');
	for(var i=0;i < ca.length;i++) {
		var c = ca[i];
		while (c.charAt(0) === ' ') {
			c = c.substring(1,c.length);
		}
		if (c.indexOf(nameEQ) === 0) {
			return c.substring(nameEQ.length,c.length);
		}
	}
	return null;
}

function setCaretPosition(ctrl, pos)
{

	if(ctrl.setSelectionRange)
	{
		ctrl.focus();
		ctrl.setSelectionRange(pos,pos);
	}
	else if (ctrl.createTextRange) {
		var range = ctrl.createTextRange();
		range.collapse(true);
		range.moveEnd('character', pos);
		range.moveStart('character', pos);
		range.select();
	}
}
