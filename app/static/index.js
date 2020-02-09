const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
var open_arc_id = current_page = total_pages = undefined;
var notifications = false;
var renamer_enabled = true;
var rename_queue = {};
const valid_options = {'convention': 'A54242', 'publisher': '8C9440', 'collections': 'DE935F', 'type': '5F819D', 'circle': '85678F', 'author': '5E8D87', 'parody': 'CC6666', 'imprint': 'B5BD68', 'genre': 'F0C674', 'character': '81A2BE', 'contents': 'B294BB', 'rating': '8ABEB7'};
var autocomplete_focus_i = -1;

function default_xhr_error(page, status, data) {
	document.open();
	document.write(data);
	document.close();
}

function get(page, success_cb, failed_cb=default_xhr_error) {
	var xhr = new XMLHttpRequest();
	xhr.open('GET', page);
	xhr.onload = function() {
		if (xhr.status === 200) {
			if (success_cb)
				success_cb(xhr.responseText);
		} else {
			if (failed_cb)
				failed_cb(page, xhr.status, xhr.responseText);
		}
	};
	xhr.send();
};

function post(page, data, success_cb, mime='application/json;charset=UTF-8') {
	var xhr = new XMLHttpRequest();
	xhr.open('POST', page);
	xhr.setRequestHeader('Content-Type', mime);
	xhr.onload = function() {
		if (xhr.status === 200) {
			if (success_cb)
				success_cb(xhr.responseText);
		} else
			default_xhr_error(page, xhr.status, xhr.responseText);
	};
	xhr.send(data);
};

function fadeIn(elem, ms) {
	if (!elem )
		return;

	elem.style.opacity = 0;
	elem.style.filter = "alpha(opacity=0)";
	elem.style.display = "inline-block";
	elem.style.visibility = "visible";

	if (ms) {
		var opacity = 0;
		var timer = setInterval(function() {
			opacity += 50 / ms;
			if (opacity >= 1) {
				clearInterval(timer);
				opacity = 1;
			}
			elem.style.opacity = opacity;
			elem.style.filter = "alpha(opacity=" + opacity * 100 + ")";
		}, 50);
	} else {
		elem.style.opacity = 1;
		elem.style.filter = "alpha(opacity=1)";
	}
}

function fadeOut(elem, ms) {
	if (!elem)
		return;

	if (ms) {
		var opacity = 1;
		var timer = setInterval(function() {
			opacity -= 50 / ms;
			if (opacity <= 0) {
				clearInterval(timer);
				opacity = 0;
				elem.style.display = "none";
				elem.style.visibility = "hidden";
			}
			elem.style.opacity = opacity;
			elem.style.filter = "alpha(opacity=" + opacity * 100 + ")";
		}, 50);
	} else {
		elem.style.opacity = 0;
		elem.style.filter = "alpha(opacity=0)";
		elem.style.display = "none";
		elem.style.visibility = "hidden";
	}
}

function combine_dicts(a, b) {
	Object.keys(b).forEach(function(key) {
		a[key] = b[key];
	});
	return a;
}

function notify(options, click_cb=null, close_cb=null, error_cb=null, show_cb=null) {
	if (!notifications)
		return null;
	var obj = {
		icon: '/static/favicon.png',
		image: '/static/favicon.png'
	};
	var n = new Notification("doujinshi-db", combine_dicts(obj, options));
	if (click_cb)
		n.onclick = click_cb;
	if (close_cb)
		n.onclose = close_cb;
	if (error_cb)
		n.onerror = error_cb;
	if (show_cb)
		n.onshow = show_cb;
}

function to_date(timestamp){
	var a = new Date(timestamp * 1000);
	var date = a.getDate();
	var date_suffix = 'th';
	switch (date) {
		case 1:
		case 21:
		case 31:
			date_suffix = 'st';
			break;
		case 2:
		case 22:
			date_suffix = 'nd';
			break;
		case 3:
		case 23:
			date_suffix = 'rd';
			break;
	}
	return date + date_suffix + ' ' + months[a.getMonth()] + ' ' + a.getFullYear();
}

function open_page() {
	get('/api/page/' + open_arc_id + '/' + current_page, function(data) {
		document.getElementById('reader_overlay').style.backgroundImage = 'url("data:image/png;base64,' + data + '")';
		document.getElementById('progress').style.width = ((((current_page + 1) / total_pages) * 100) + '%');
		document.getElementById('pages').innerHTML = "<h1>" + (current_page + 1) + " / " + total_pages + "</h1>";
	});
}

function next_rename() {
	delete rename_queue[Object.keys(rename_queue)[0]];
	if (!Object.keys(rename_queue).length) {
		document.getElementById('rename_queue_len').style.display = 'none';
		fadeOut(document.getElementById('rename_overlay'), 150);
		return;
	}
	document.getElementById('log_button').click();
}

function add_autocomplete(data, cb) {
	var a = document.getElementById('autocomplete-list');
	data.forEach(function(d) {
		b = document.createElement("div");
		b.setAttribute('class', 'autocomplete-item');
		b.innerHTML = d;
		b.addEventListener('mousedown', cb);
		a.appendChild(b);
	});
}

function clear_autocomplete() {
	autocomplete_focus_i = -1;
	var elements = document.getElementsByClassName('autocomplete-item');
	while (elements.length > 0)
		elements[0].parentNode.removeChild(elements[0]);
}

function add_autocomplete_tag(a, b) {
	var c = a + ':' + b;
	var x = document.querySelectorAll('.tag');
	for (var i = 0; i < x.length; i++)
		if (x[i].innerHTML === c)
			return;
	var t = document.createElement('div')
	t.setAttribute('class', 'tag');
	t.innerHTML = c;
	t.style.backgroundColor = '#' + valid_options[a];
	t.addEventListener('mousedown', function(e) {
		e.preventDefault();
		t.parentNode.removeChild(t);
	});
	var l = document.getElementById('autocomplete-list');
	l.insertBefore(t, l.firstChild);
}

function autocomplete_search_json(s) {
	var out = {'tags': {}, 'search': s};
	var x = document.querySelectorAll('.tag');
	for (var i = 0; i < x.length; i++) {
		var a = x[i].innerHTML.split(':');
		if (!Object.keys(out['tags']).includes(a[0]))
			out['tags'][a[0]] = [];
		out['tags'][a[0]].push(a.slice(1).join(':').trim());
	}
	return JSON.stringify(out);
}

document.addEventListener('DOMContentLoaded', function() {
	if ("Notification" in window) {
		switch (Notification.permission) {
			case 'granted':
				notifications = true;
				break;
			case 'denied':
				notifications = false;
				break;
			case 'default':
				notifications = false;
				Notification.requestPermission(function (permission) {
					notifications = (permission === "granted");
				});
				break;
		}
	}

	var timer_ticks = 1000;
	var timer = setTimeout(function queue_worker() {
		get('/api/queue', function(data) {
			if (!renamer_enabled) {
				timer_ticks += 5000;
				return;
			}
			var n = Object.keys(rename_queue).length;
			rename_queue = JSON.parse(data);
			var nn = Object.keys(rename_queue).length;
			if (!nn) {
				document.getElementById('rename_queue_len').style.display = 'none';
				timer_ticks += 1000;
			} else {
				if (nn > n) {
					notify({body: nn + ' archive' + (nn === 1 ? '' : 's') + ' to check!'});
					timer_ticks = 1000;
				} else
					timer_ticks += 500;
				document.getElementById('rename_queue_len').style.display = 'block';
			}
		});
		timer = setTimeout(queue_worker, timer_ticks);
	}, 1000);

	document.getElementById('title').addEventListener('click', function(e) {
		window.location = '/';
	});

	document.querySelectorAll('.item').forEach(function(a) {
		get('/api/cover/' + a.id, function(data) {
			document.getElementById(a.id).querySelector('img').src = 'data:image/png;base64,' + data;
		});
	});

	document.querySelectorAll('.item').forEach(function(item) {
		item.addEventListener('click', function(e) {
			if (item.querySelector('img').src.split('/').pop() === 'loading.gif')
				return;
			var data = JSON.parse(this.querySelector('p').innerHTML);
			for (var key in data) {
				switch (key) {
					case 'path':
					case 'title':
					case 'pages':
					case 'bid':
						document.getElementById(key + '_val').innerHTML = data[key];
						break;
					case 'date':
						document.getElementById(key + '_val').innerHTML = to_date(data[key]);
						break;
					case 'rating':
						document.getElementById('rating_val_select').value = data[key];
						break;
					default:
						document.getElementById(key + '_val').innerHTML = (data[key].split('|').map(function(x) {
							return '<span class="search_me" id="' + key + '">' + x + '</span>';
						}).join(', '));
						break;
					case 'cover':
						document.getElementById('info_cover').style.backgroundImage = 'url("' + this.querySelector('img').src + '")';
						break;
				}
			}
			fadeIn(document.getElementById('info_overlay'), 150);
		});
	});

	document.getElementById('info_overlay').addEventListener('click', function(e) {
		switch (e.target.className) {
			case 'search_me':
				window.location = "/" + e.target.id + "/" + e.target.innerHTML;
				break;
			case 'overlay':
				fadeOut(e.target, 150);
				document.getElementById('info_cover').style.backgroundImage = '';
				break;
			default:
				e.stopPropagation();
				break;
		}
	});

	document.getElementById('option_select').addEventListener('change', function(e) {
		var val = e.target.value;
		var tag_select = document.getElementById('tag_select');
		tag_select.innerHTML = '<option value="0">Select a category...</option>';
		switch (val) {
			case "0":
				break;
			case "rating":
				for (var i = 1; i < 6; i++)
					tag_select.insertAdjacentHTML('beforeend', "<option value='" + i + "'>" + i + "</option>");
				break;
			default:
				get('/api/info/' + val, function(data) {
					data = JSON.parse(data);
					data.forEach(function(d) {
						tag_select.insertAdjacentHTML('beforeend', "<option value='" + d + "'>" + d + "</option>");
					});
				});
				break;
		}
	});

	document.getElementById('tag_select').addEventListener('change', function(e) {
		var val = this.value;
		if (val !== "0")
			window.location = "/" + document.getElementById('option_select').value + "/" + val;
	});

	document.getElementById('button_web').addEventListener('click', function(e) {
		get('/api/open/web/' + document.getElementById('bid_val').innerHTML, function(data) {
			data = JSON.parse(data);
			open_arc_id  = data['id'];
			total_pages	 = data['pages'];
			current_page = 0;
			open_page();
			fadeOut(document.getElementById('info_overlay'), 150);
			fadeIn(document.getElementById('reader_overlay'), 150);
		});
	});

	document.getElementById('button_cli').addEventListener('click', function(e) {
		get('/api/open/remote/' + document.getElementById('bid_val').innerHTML);
	});

	document.getElementById('right').addEventListener('click', function(e) {
		e.stopPropagation();
		if (current_page < total_pages - 1) {
			current_page += 1;
			open_page();
		}
	});

	document.getElementById('left').addEventListener('click', function(e) {
		e.stopPropagation();
		if (current_page > 0) {
			current_page -= 1;
			open_page();
		}
	});

	document.getElementById('cancel').addEventListener('click', function(e) {
		e.stopPropagation();
		fadeOut(document.getElementById('reader_overlay'), 150);
		get('/api/close/' + open_arc_id);
		open_arc_id = undefined;
		document.getElementById('reader_overlay').style.backgroundImage = '';
	});

	document.getElementById('reader_overlay').addEventListener('click', function(e) {
		var rect = e.target.getBoundingClientRect();
		if (e.clientX - rect.left > rect.width / 2)
			document.getElementById('right').click();
		else
			document.getElementById('left').click();
	});

	document.getElementById('rating_val_select').addEventListener('change', function(e) {
		get('/api/rate/' + document.getElementById('bid_val').innerHTML + '/' + e.target.value);
	});

	document.addEventListener('keydown', function(e) {
		if (typeof open_arc_id !== 'undefined') {
			switch (e.which) {
				case 37:
				case 8:
					document.getElementById('left').click();
					break;
				case 39:
				case 32:
					document.getElementById('right').click();
					break;
				case 27:
					document.getElementById('cancel').click();
					break;
			}
		}
	});

	document.getElementById('delete_doujin').addEventListener('click', function(e) {
		var bid = document.getElementById('bid_val').innerHTML;
		if (confirm('Do you want to delete ' + bid + '?'))
			get('/api/delete/' + bid, function(data) {
				location.reload();
			});
	});

	document.getElementById('log_button').addEventListener('click', function(e) {
		if (Object.keys(rename_queue).length) {
			var first = rename_queue[Object.keys(rename_queue)[0]];
			document.getElementById('a').style.backgroundImage = 'url("data:image/png;base64,' + first['cover'] + '")'; 
			for (var i = 98; i < 101; i++) {
				var j = i - 98;
				var x = document.getElementById(String.fromCharCode(i));
				x.querySelector('.rename_tag').innerHTML = first['match'][j]['match'] + '%';
				x.style.backgroundImage = 'url("' + first['match'][j]['cover_url'] + '")';
			}
			fadeIn(document.getElementById('rename_overlay'), 150);
		}
	});

	document.getElementById('cancel_rename').addEventListener('click', function(e) {
		fadeOut(document.getElementById('rename_overlay'), 150);
	});

	document.querySelectorAll('.rename_me').forEach(function(item) {
		item.addEventListener('click', function(e) {
			var id = Object.keys(rename_queue)[0];
			switch(item.id) {
				case 'a':
					if (confirm('Do you want to skip renaming this doujin?'))
						get('/api/queue/' + id + '/0', next_rename);
					break;
				case 'b':
				case 'c':
				case 'd':
					console.log(item.id.charCodeAt(0) - 97);
					if (confirm('Are you sure you want to use doujin ' + item.id.toUpperCase() + '?'))
						get('/api/queue/' + id + '/' + (item.id.charCodeAt(0) - 97), next_rename);
					break;
			}
		});
	});

	var search = document.getElementById('search');
	search.addEventListener('focus', function(e) {
		document.getElementById('autocomplete-list').style.display = 'block';
	});
	search.addEventListener('blur', function(e) {
		var y = document.getElementById('autocomplete-list');
		y.style.display = 'none';
		autocomplete_focus_i = -1;
		var x = y.querySelectorAll('.autocomplete-item');
		for (var i = 0; i < x.length; i++)
			x[i].classList.remove("autocomplete-active");
	});
	search.addEventListener('input', function(e) {
		clear_autocomplete();
		var val = search.value;
		if (!val)
			return;

		switch(val.charAt(0)) {
			case '#':
				a = val.split(':');
				if (a.length === 1)
					return;
				b = a.slice(1).join(':').trim();
				a = a[0].slice(1);
				if (!Object.keys(valid_options).includes(a))
					return;
				var c = (b.length ? '/api/autocomplete/tag/' + a + '/' + b : '/api/info/' + a);
				get(c, function(data) {
					add_autocomplete(JSON.parse(data), function(e) {
						e.preventDefault();
						var a = search.value.split(':')[0].slice(1);
						var b = e.target.innerHTML;
						get('/api/autocomplete/check/' + a + '/' + b, function(data) {
							clear_autocomplete();
							if (data === 'yes')
								add_autocomplete_tag(a, b);
							search.value = '';
							search.focus();
						});
					});
				});
				break;
			case '?':
				a = val.slice(1)
				if (!a.length)
					return;
				get('/api/autocomplete/unknown/' + a, function(data) {
					add_autocomplete(JSON.parse(data), function(e) {
						e.preventDefault();
						clear_autocomplete();
						var a = e.target.innerHTML.split(':');
						add_autocomplete_tag(a[0], a.slice(1).join(':').trim());
						search.value = '';
						search.focus();
					});
				});
				break;
			default:
				post('/api/autocomplete/regular', autocomplete_search_json(search.value), function(data) {
					clear_autocomplete();
					add_autocomplete(JSON.parse(data), function(e) {
						document.getElementById('search_json').value = autocomplete_search_json(e.target.innerHTML);
						document.getElementById('search_one').value = 'yes';
						document.getElementById('search_form').submit();
					});
				});
				break;
		}
	});
	search.addEventListener('keydown', function(e) {
		var y = document.getElementById('autocomplete-list');
		var x = y.querySelectorAll('.autocomplete-item');
		switch (e.keyCode) {
			case 40:
				e.preventDefault();
				autocomplete_focus_i++;
				break;
			case 38:
				e.preventDefault();
				autocomplete_focus_i--;
				break;
			case 13:
				if (autocomplete_focus_i < 0 || !x.length) {
					document.getElementById('search_json').value = autocomplete_search_json(search.value);
					document.getElementById('search_form').submit();
				} else
					x[autocomplete_focus_i].dispatchEvent(new Event('mousedown'));
				return;
		}
		if (autocomplete_focus_i < 0)
			autocomplete_focus_i = 0;
		if (autocomplete_focus_i >= x.length)
			autocomplete_focus_i = x.length - 1;
		if (!x.length)
			return;
		for (var i = 0; i < x.length; i++)
			x[i].classList.remove("autocomplete-active");
		x[autocomplete_focus_i].classList.add("autocomplete-active");
		x[autocomplete_focus_i].scrollIntoView();
	});
});
