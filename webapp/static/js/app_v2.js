const API = '/api';

const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor('bg_color');
    tg.setBackgroundColor('bg_color');
}

function showAlert(msg) {
    if (tg?.showAlert) tg.showAlert(String(msg));
    else alert(msg);
}

function showConfirm(msg, callback) {
    if (tg?.showConfirm) tg.showConfirm(String(msg), callback);
    else callback(confirm(msg));
}

const state = {
    userId: tg?.initDataUnsafe?.user?.id || new URLSearchParams(window.location.search).get('user_id') || '0',
    currentTab: 'feed',
    currentFilter: 'all',
    user: null,
    promo: null,
    orders: [],
    map: null,
    markers: [],
};

console.log('WebApp init, userId:', state.userId);

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadProfile();
    loadPromo();
    switchTab('feed');
});

function initNavigation() {
    document.querySelectorAll('.bottom-nav button').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
}

function switchTab(tab) {
    state.currentTab = tab;
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.bottom-nav button').forEach(btn => btn.classList.remove('active'));
    document.getElementById('tab-' + tab)?.classList.add('active');
    document.querySelector('.bottom-nav button[data-tab="' + tab + '"]')?.classList.add('active');

    if (tab === 'feed') loadFeed();
    else if (tab === 'map') initMap();
    else if (tab === 'create') initCreateForm();
    else if (tab === 'profile') renderProfile();
}

async function api(path, opts) {
    opts = opts || {};
    var sep = path.includes('?') ? '&' : '?';
    var url = API + path + sep + 'user_id=' + state.userId;
    console.log('API:', opts.method || 'GET', url);
    try {
        var resp = await fetch(url, {
            method: opts.method || 'GET',
            headers: { 'Content-Type': 'application/json' },
            body: opts.body ? JSON.stringify(opts.body) : undefined,
        });
        var text = await resp.text();
        console.log('API status:', resp.status, 'body:', text);
        try {
            return JSON.parse(text);
        } catch (e) {
            console.error('Not JSON:', text.substring(0, 200));
            return { error: 'server_error_' + resp.status };
        }
    } catch (err) {
        console.error('API err:', err);
        return { error: err.message || 'network_error' };
    }
}

async function loadFeed() {
    var container = document.getElementById('feed-list');
    container.innerHTML = '<div class="loading">Загрузка...</div>';
    var typeParam = state.currentFilter !== 'all' ? '?type_filter=' + state.currentFilter : '';
    state.orders = await api('/orders/feed' + typeParam);
    renderFeed();
}

function renderFeed() {
    var container = document.getElementById('feed-list');
    if (!Array.isArray(state.orders) || !state.orders.length) {
        container.innerHTML = '<div class="empty-state"><div class="icon"></div><p>Нет активных заказов</p></div>';
        return;
    }
    container.innerHTML = state.orders.map(orderCard).join('');
}

function orderCard(o) {
    var typeClass = o.type === 'freight' ? 'freight' : 'passenger';
    var typeLabel = o.type === 'freight' ? 'Груз' : 'Пассажиры';
    var dt = new Date(o.date_time);
    var dateStr = dt.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) + ' ' + dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

    return '<div class="order-card" data-id="' + o.id + '">' +
        '<div class="card-header">' +
            '<span class="card-type ' + typeClass + '">' + typeLabel + '</span>' +
            '<span class="card-price">' + o.price + ' ₴</span>' +
        '</div>' +
        '<div class="card-route">' + o.from_text + ' → ' + o.to_text + '</div>' +
        '<div class="card-date">' + dateStr + '</div>' +
        (o.road_distance_km ? '<div style="font-size:12px;color:var(--tg-text-secondary);margin-top:4px">' + o.road_distance_km + ' км по дороге</div>' : '') +
        (o.description ? '<div class="card-desc">' + o.description + '</div>' : '') +
        '<div class="card-footer">' +
            '<span style="font-size:12px;color:var(--tg-text-secondary)">#' + o.id + '</span>' +
            '<button class="btn btn-primary btn-sm" onclick="openBidModal(' + o.id + ')">Откликнуться</button>' +
        '</div>' +
    '</div>';
}

function setFilter(filter) {
    state.currentFilter = filter;
    document.querySelectorAll('#tab-feed .filter-chip').forEach(function(el) {
        el.classList.toggle('active', el.dataset.filter === filter);
    });
    loadFeed();
}

function initMap() {
    if (state.map) {
        state.map.invalidateSize();
        loadMapOrders();
        return;
    }

    if (!navigator.geolocation) {
        initMapFallback();
        return;
    }

    navigator.geolocation.getCurrentPosition(function(pos) {
        var lat = pos.coords.latitude;
        var lng = pos.coords.longitude;
        initMapAt(lat, lng);
    }, function() {
        initMapFallback();
    });
}

function initMapFallback() {
    initMapAt(49.9935, 36.2304);
}

function initMapAt(lat, lng) {
    state.map = L.map('map').setView([lat, lng], 10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(state.map);

    L.marker([lat, lng]).addTo(state.map).bindPopup('Вы здесь').openPopup();
    L.circle([lat, lng], { radius: 150000, color: '#3b82f6', fillOpacity: 0.05, weight: 1 }).addTo(state.map);

    state.userLat = lat;
    state.userLng = lng;

    setTimeout(function() { state.map.invalidateSize(); }, 200);
    loadMapOrders();
}

function haversineKm(lat1, lng1, lat2, lng2) {
    var R = 6371;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLng = (lng2 - lng1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

async function loadMapOrders() {
    if (!state.userLat) return;
    var orders = await api('/orders/map?lat=' + state.userLat + '&lng=' + state.userLng + '&radius=150');

    state.markers.forEach(function(m) { state.map.removeLayer(m); });
    state.markers = [];

    if (!Array.isArray(orders)) return;

    orders.forEach(function(o) {
        var isFreight = o.type === 'freight';
        var color = isFreight ? '#3b82f6' : '#22c55e';
        var bgColor = isFreight ? '#dbeafe' : '#dcfce7';
        var svg = isFreight
            ? '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="' + color + '" width="28" height="28"><path d="M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm13.5-9l1.96 2.5H17V9.5h2.5zm-1.5 9c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>'
            : '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="' + color + '" width="28" height="28"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>';

        var startIcon = L.divIcon({
            className: '',
            html: '<div style="background:' + bgColor + ';border:2px solid ' + color + ';border-radius:8px;width:38px;height:38px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.3)">' + svg + '</div>',
            iconSize: [38, 38],
            iconAnchor: [19, 19],
            popupAnchor: [0, -22]
        });

        var endIcon = L.divIcon({
            className: '',
            html: '<div style="background:#fef3c7;border:2px solid #f59e0b;border-radius:8px;width:38px;height:38px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.3)"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f59e0b" width="28" height="28"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg></div>',
            iconSize: [38, 38],
            iconAnchor: [19, 38],
            popupAnchor: [0, -30]
        });

        var routeKm = o.road_distance_km || haversineKm(o.from_lat, o.from_lng, o.to_lat, o.to_lng);

        var startMarker = L.marker([o.from_lat, o.from_lng], {icon: startIcon}).addTo(state.map);
        startMarker.bindPopup(
            '<div style="min-width:180px">' +
            '<div style="font-size:11px;color:#666;margin-bottom:2px">Откуда</div>' +
            '<b>' + o.from_text + '</b><hr style="margin:4px 0;border-color:#eee">' +
            '<div style="font-size:11px;color:#666;margin-bottom:2px">Куда</div>' +
            '<b>' + o.to_text + '</b><hr style="margin:4px 0;border-color:#eee">' +
            '<div style="display:flex;justify-content:space-between"><span><b>' + o.price + ' &#8372;</b></span><span style="color:#666">' + routeKm + ' км</span></div>' +
            '<div style="font-size:11px;color:#666;margin-top:2px">От вас: ' + o.distance_km + ' км</div>' +
            '<button class="btn btn-primary btn-sm" style="margin-top:8px;width:100%" onclick="openBidModal(' + o.id + ')">Откликнуться</button>' +
            '</div>'
        );
        state.markers.push(startMarker);

        var endMarker = L.marker([o.to_lat, o.to_lng], {icon: endIcon}).addTo(state.map);
        endMarker.bindPopup(
            '<b>' + o.to_text + '</b><br>' +
            '<span style="color:#666;font-size:12px">Пункт назначения заказа #' + o.id + '</span>'
        );
        state.markers.push(endMarker);

        if (o.route_geometry) {
            var coords = o.route_geometry.split(';').map(function(c) {
                var p = c.split(',');
                return [parseFloat(p[0]), parseFloat(p[1])];
            });
            var line = L.polyline(coords, {color: color, weight: 3, opacity: 0.7}).addTo(state.map);
            state.markers.push(line);
        } else {
            var line = L.polyline([[o.from_lat, o.from_lng], [o.to_lat, o.to_lng]], {
                color: color, weight: 3, opacity: 0.7, dashArray: '8, 6'
            }).addTo(state.map);
            state.markers.push(line);
        }
    });
}

var createType = 'freight';

function setCreateType(type) {
    createType = type;
    document.querySelectorAll('#tab-create .toggle-group button').forEach(function(btn) {
        btn.classList.toggle('active', btn.dataset.type === type);
    });
}

function initCreateForm() {
    var form = document.getElementById('create-form');
    if (form) {
        form.onsubmit = async function(e) {
            e.preventDefault();
            await submitOrder();
        };
    }
}

async function submitOrder() {
    var from = document.getElementById('create-from').value.trim();
    var to = document.getElementById('create-to').value.trim();
    var dateVal = document.getElementById('create-date').value;
    var price = parseInt(document.getElementById('create-price').value);
    var desc = document.getElementById('create-desc').value.trim();

    console.log('Submit order:', { from: from, to: to, date: dateVal, price: price, type: createType });

    if (!from || !to || !dateVal || !price) {
        showAlert('Заполните все обязательные поля');
        return;
    }

    showAlert('Геокодируем адреса...');

    var fromGeo = await geocode(from);
    var toGeo = await geocode(to);

    if (!fromGeo || !toGeo) {
        showAlert('Не удалось определить координаты. Укажите город точнее (напр. Харьков, Киев).');
        return;
    }

    console.log('Geocoded:', fromGeo, toGeo);

    var result = await api('/orders', {
        method: 'POST',
        body: {
            type: createType,
            from_text: from,
            to_text: to,
            from_lat: fromGeo.lat,
            from_lng: fromGeo.lng,
            to_lat: toGeo.lat,
            to_lng: toGeo.lng,
            date_time: new Date(dateVal).toISOString(),
            price: price,
            description: desc || null,
        },
    });

    console.log('Create result:', result);

    if (result && result.ok) {
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
        showAlert('Заказ создан!');
        document.getElementById('create-form').reset();
        switchTab('feed');
    } else {
        showAlert('Ошибка: ' + (result?.error || 'неизвестная'));
    }
}

async function geocode(address) {
    var data = await api('/geocode?address=' + encodeURIComponent(address));
    if (data && data.lat) return { lat: data.lat, lng: data.lng };
    console.error('Geocode failed:', address, data);
    return null;
}

async function openBidModal(orderId) {
    var order = await api('/orders/' + orderId);
    if (!order || order.error) {
        showAlert('Заказ не найден');
        return;
    }

    var modal = document.getElementById('bid-modal');
    var body = document.getElementById('bid-modal-body');
    var dt = new Date(order.date_time);

    body.innerHTML =
        '<h3>Отклик на заказ #' + order.id + '</h3>' +
        '<div class="order-card" style="margin:12px 0">' +
            '<div class="card-route">' + order.from_text + ' → ' + order.to_text + '</div>' +
            '<div class="card-date">' + dt.toLocaleDateString('ru-RU') + ' ' + dt.toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) + '</div>' +
            (order.road_distance_km ? '<div style="font-size:12px;color:var(--tg-text-secondary);margin-top:4px">' + order.road_distance_km + ' км по дороге</div>' : '') +
            '<div class="card-price" style="margin-top:6px">Бюджет клиента: ' + order.price + ' ₴</div>' +
        '</div>' +
        '<div class="form-group">' +
            '<label>Ваша цена (₴)</label>' +
            '<input type="number" id="bid-price" value="' + order.price + '" min="1">' +
        '</div>' +
        '<p style="font-size:12px;color:var(--tg-text-secondary);margin-bottom:12px">' +
            'Оставьте цену как есть, чтобы принять бюджет клиента, или измените для торга.' +
        '</p>' +
        '<div style="display:flex;gap:8px">' +
            '<button class="btn btn-primary" style="flex:1" onclick="submitBid(' + order.id + ')">Отправить</button>' +
            '<button class="btn btn-outline" onclick="closeBidModal()">Закрыть</button>' +
        '</div>' +
        '<div id="bids-section" style="margin-top:16px"></div>';

    modal.classList.add('show');
    loadExistingBids(orderId);
}

async function loadExistingBids(orderId) {
    var bids = await api('/orders/' + orderId + '/bids');
    var section = document.getElementById('bids-section');
    if (!Array.isArray(bids) || !bids.length) {
        section.innerHTML = '';
        return;
    }
    var html = '<h4 style="font-size:14px;margin-bottom:8px">Отклики (' + bids.length + ')</h4>';
    bids.forEach(function(b) {
        html += '<div class="bid-item">' +
            '<div class="bid-driver">' + b.driver_name + ' (рейтинг: ' + b.driver_rating + ')</div>' +
            '<div style="display:flex;align-items:center;gap:8px">' +
                '<span class="bid-price">' + b.proposed_price + ' &#8372;</span>' +
                (b.status === 'pending' && String(b.driver_id) !== String(state.userId)
                    ? '<button class="btn btn-success btn-sm" onclick="respondBid(' + b.bid_id + ', \'accept\')">Принять</button> ' +
                      '<button class="btn btn-danger btn-sm" onclick="respondBid(' + b.bid_id + ', \'reject\')">Отклонить</button>'
                    : '<span style="font-size:11px;color:var(--tg-text-secondary)">' + b.status + '</span>') +
            '</div>' +
        '</div>';
    });
    section.innerHTML = html;
}

function closeBidModal() {
    document.getElementById('bid-modal').classList.remove('show');
}

async function submitBid(orderId) {
    var price = parseInt(document.getElementById('bid-price').value);
    if (!price || price < 1) return;

    var result = await api('/bids', {
        method: 'POST',
        body: { order_id: orderId, proposed_price: price },
    });

    if (result && result.ok) {
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
        showAlert('Отклик отправлен!');
        loadExistingBids(orderId);
    } else {
        showAlert(result?.error || 'Ошибка');
    }
}

async function respondBid(bidId, action) {
    var result = await api('/bids/respond', {
        method: 'POST',
        body: { bid_id: bidId, action: action },
    });
    if (result && result.ok) {
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
        showAlert(action === 'accept' ? 'Водитель выбран!' : 'Отклонено');
        closeBidModal();
        if (state.currentTab === 'feed') loadFeed();
    } else {
        showAlert(result?.error || 'Ошибка');
    }
}

async function loadProfile() {
    state.user = await api('/user/' + state.userId);
    state.promo = await api('/stats/promo');
    renderProfile();
}

function renderProfile() {
    var container = document.getElementById('profile-content');
    if (!state.user || state.user.error) {
        container.innerHTML = '<div class="empty-state"><div class="icon"></div><p>Откройте приложение через Telegram</p></div>';
        return;
    }
    var u = state.user;
    var p = state.promo || { completed: 0, limit: 150, is_promo_active: true };
    var progress = Math.min((p.completed / p.limit) * 100, 100);

    container.innerHTML =
        '<div class="profile-header">' +
            '<div class="profile-avatar">' + (u.full_name || u.username || 'U')[0].toUpperCase() + '</div>' +
            '<div class="profile-name">' + (u.full_name || u.username || 'User ' + u.id) + '</div>' +
            '<div style="color:var(--tg-text-secondary);font-size:13px">@' + (u.username || 'no_username') + '</div>' +
            '<div class="profile-stats">' +
                '<div class="profile-stat">' +
                    '<div class="value">' + u.rating.toFixed(1) + '</div>' +
                    '<div class="label">Рейтинг</div>' +
                '</div>' +
                '<div class="profile-stat">' +
                    '<div class="value">' + u.deals_completed + '</div>' +
                    '<div class="label">Сделок</div>' +
                '</div>' +
            '</div>' +
        '</div>' +
        '<div class="promo-box">' +
            '<h3>Акция MVP: Комиссия — 0%</h3>' +
            '<p>Выполнено бесплатных сделок: ' + p.completed + ' / ' + p.limit + '</p>' +
            '<div class="promo-progress">' +
                '<div class="promo-progress-bar" style="width:' + progress + '%"></div>' +
            '</div>' +
        '</div>' +
        '<div style="margin:16px 0">' +
            '<h4 style="font-size:14px;margin-bottom:8px">Мой транспорт</h4>' +
            '<div id="vehicles-list"></div>' +
            '<button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="showAddVehicle()">+ Добавить транспорт</button>' +
        '</div>' +
        '<div class="toggle-group" style="margin:16px 0">' +
            '<button data-role="client" class="' + (u.role === 'client' ? 'active' : '') + '" onclick="setRole(\'client\')">Клиент</button>' +
            '<button data-role="driver" class="' + (u.role === 'driver' ? 'active' : '') + '" onclick="setRole(\'driver\')">Водитель</button>' +
            '<button data-role="both" class="' + (u.role === 'both' ? 'active' : '') + '" onclick="setRole(\'both\')">Оба</button>' +
        '</div>' +
        '<div class="spoiler" onclick="this.classList.toggle(\'open\')">' +
            '<div class="spoiler-header">Как пользоваться сервисом <span>▼</span></div>' +
            '<div class="spoiler-body">' +
                '<b>Для пассажиров / грузоотправителей:</b><br>' +
                '1. Создайте заказ во вкладке «Создать»<br>' +
                '2. Укажите маршрут, дату и бюджет<br>' +
                '3. Ожидайте откликов водителей<br><br>' +
                '<b>Для водителей / перевозчиков:</b><br>' +
                '1. Найдите заказ в «Ленте» или на «Карте»<br>' +
                '2. Нажмите «Откликнуться» и предложите цену<br>' +
                '3. После принятия свяжитесь с клиентом' +
            '</div>' +
        '</div>' +
        '<div id="vehicles-container"></div>';

    loadVehicles();
}

async function loadVehicles() {
    var vehicles = await api('/vehicles');
    var container = document.getElementById('vehicles-container');
    if (!Array.isArray(vehicles) || !vehicles.length) return;

    var html = '<div style="margin-top:12px">';
    var typeIcons = { car: '', minivan: '', truck_3_5t: '', heavy_truck: '' };
    vehicles.forEach(function(v) {
        html += '<div class="vehicle-card">' +
            '<div class="vehicle-info">' +
                v.make_model + '<br>' +
                '<span class="vehicle-plate">' + v.license_plate + '</span>' +
                (v.capacity_kg ? ' | ' + v.capacity_kg + ' кг' : '') +
                (v.capacity_seats ? ' | ' + v.capacity_seats + ' мест' : '') +
            '</div>' +
            '<button class="btn btn-danger btn-sm" onclick="deleteVehicle(' + v.id + ')">Удалить</button>' +
        '</div>';
    });
    html += '</div>';
    container.innerHTML = html;
}

function showAddVehicle() {
    var modal = document.getElementById('bid-modal');
    var body = document.getElementById('bid-modal-body');
    body.innerHTML =
        '<h3>Добавить транспорт</h3>' +
        '<form id="vehicle-form" onsubmit="submitVehicle(event)">' +
            '<div class="form-group">' +
                '<label>Тип</label>' +
                '<select id="v-type">' +
                    '<option value="car">Легковой</option>' +
                    '<option value="minivan">Минивэн</option>' +
                    '<option value="truck_3_5t">Грузовик до 3.5т</option>' +
                    '<option value="heavy_truck">Тяжелый грузовик</option>' +
                '</select>' +
            '</div>' +
            '<div class="form-group">' +
                '<label>Марка / Модель</label>' +
                '<input type="text" id="v-make" required placeholder="Toyota Camry">' +
            '</div>' +
            '<div class="form-group">' +
                '<label>Госномер</label>' +
                '<input type="text" id="v-plate" required placeholder="АА 1234 БВ">' +
            '</div>' +
            '<div class="form-group">' +
                '<label>Грузоподъемность (кг)</label>' +
                '<input type="number" id="v-kg" placeholder="0">' +
            '</div>' +
            '<div class="form-group">' +
                '<label>Кол-во мест</label>' +
                '<input type="number" id="v-seats" placeholder="0">' +
            '</div>' +
            '<button class="btn btn-primary" type="submit" style="width:100%">Добавить</button>' +
        '</form>';
    modal.classList.add('show');
}

async function submitVehicle(e) {
    e.preventDefault();
    var result = await api('/vehicles', {
        method: 'POST',
        body: {
            type: document.getElementById('v-type').value,
            make_model: document.getElementById('v-make').value,
            license_plate: document.getElementById('v-plate').value,
            capacity_kg: parseInt(document.getElementById('v-kg').value) || null,
            capacity_seats: parseInt(document.getElementById('v-seats').value) || null,
        },
    });
    if (result && result.ok) {
        showAlert('Транспорт добавлен!');
        closeBidModal();
        loadVehicles();
    } else {
        showAlert(result?.error || 'Ошибка');
    }
}

function deleteVehicle(id) {
    showConfirm('Удалить транспорт?', async function(ok) {
        if (!ok) return;
        await api('/vehicles/' + id, { method: 'DELETE' });
        loadVehicles();
    });
}

async function setRole(role) {
    await api('/user/role', { method: 'POST', body: { role: role } });
    state.user.role = role;
    renderProfile();
}
