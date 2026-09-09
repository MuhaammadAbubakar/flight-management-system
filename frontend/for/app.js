/**
 * Mera Safar - Application Controller
 * Handles flight search, booking workflows, live refund calculations,
 * in-flight radar animation, and strict authentication gating.
 */

const app = {
  activeTab: 'home',
  flightsCache: [],
  selectedFlightForBooking: null,
  currentPricesCache: {},
  isBoosted: false,
  telemetryInterval: null,

  // =========================================================================
  // Initialization
  // =========================================================================
  init() {
    this.setupAuthUI();
    this.initFlightTelemetry();

    // Default to 'home' if unauthenticated; if authenticated, allow search or url param
    const user = api.getCurrentUser();
    if (!user) {
      this.switchTab('home');
    } else {
      this.loadAllFlights();
      this.checkUrlParams();
    }

    // Default departure time in admin modal to tomorrow 10:00 AM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(10, 0, 0, 0);
    const isoDate = tomorrow.toISOString().slice(0, 16);
    const depInput = document.getElementById('admin-new-dep-time');
    if (depInput) depInput.value = isoDate;
  },

  checkUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    if (tab && ['home', 'search', 'bookings', 'guide', 'admin'].includes(tab)) {
      this.switchTab(tab);
    }
  },

  // =========================================================================
  // In-Flight Radar Telemetry Animation
  // =========================================================================
  initFlightTelemetry() {
    if (this.telemetryInterval) clearInterval(this.telemetryInterval);
    this.telemetryInterval = setInterval(() => {
      const altEl = document.getElementById('hud-altitude');
      const spdEl = document.getElementById('hud-airspeed');
      if (!altEl || !spdEl) return;

      if (!this.isBoosted) {
        const baseAlt = 38000;
        const deltaAlt = Math.floor((Math.random() - 0.5) * 120);
        altEl.textContent = `${(baseAlt + deltaAlt).toLocaleString()} FT`;

        const baseSpd = 512;
        const deltaSpd = Math.floor((Math.random() - 0.5) * 6);
        spdEl.textContent = `${baseSpd + deltaSpd} KTS / MACH 0.84`;
      }
    }, 3500);
  },

  toggleBoostCruiser() {
    this.isBoosted = !this.isBoosted;
    const cruiser = document.getElementById('main-airplane-cruiser');
    const trail1 = document.getElementById('contrail-engine-1');
    const trail2 = document.getElementById('contrail-engine-2');
    const altEl = document.getElementById('hud-altitude');
    const spdEl = document.getElementById('hud-airspeed');
    const label = document.getElementById('boost-btn-label');

    if (this.isBoosted) {
      if (cruiser) cruiser.classList.add('boosted');
      if (trail1) trail1.classList.add('boost');
      if (trail2) trail2.classList.add('boost');
      if (altEl) altEl.textContent = '43,000 FT (FL430)';
      if (spdEl) spdEl.textContent = '680 KTS / MACH 0.94';
      if (label) label.textContent = 'Disengage Boost';
      this.showToast('🚀 Supersonic Afterburners Engaged! Cruising at Mach 0.94', 'success');
    } else {
      if (cruiser) cruiser.classList.remove('boosted');
      if (trail1) trail1.classList.remove('boost');
      if (trail2) trail2.classList.remove('boost');
      if (altEl) altEl.textContent = '38,000 FT';
      if (spdEl) spdEl.textContent = '512 KTS / MACH 0.84';
      if (label) label.textContent = 'Afterburner Boost';
      this.showToast('Cruiser returned to standard Mach 0.84 flight profile.', 'info');
    }
  },

  // =========================================================================
  // Navigation & Tabs with Strict Authentication Guard
  // =========================================================================
  switchTab(tabName) {
    const user = api.getCurrentUser();

    // STRICT LOCK: Nobody can access any tab or function without logging in first
    if (!user && tabName !== 'home') {
      this.requireAuthPrompt(tabName);
      return;
    }

    this.activeTab = tabName;

    // Update buttons
    document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active'));
    const targetBtn = document.getElementById(`tab-btn-${tabName}`);
    if (targetBtn) targetBtn.classList.add('active');

    // Update views
    document.querySelectorAll('.tab-view').forEach(view => {
      view.style.display = 'none';
      view.classList.remove('active');
    });

    const targetView = document.getElementById(`view-${tabName}`);
    if (targetView) {
      targetView.style.display = 'block';
      targetView.classList.add('active');
    }

    // Scroll to top of view
    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (tabName === 'admin') {
      this.loadAdminFlights();
    } else if (tabName === 'search') {
      this.loadAllFlights();
    } else if (tabName === 'bookings') {
      if (user && user.email) {
        document.getElementById('lookup-email').value = user.email;
        this.lookupBookingsForEmail(user.email);
      }
    }
  },

  requireAuthPrompt(intendedTab = '') {
    this.showToast('Please Sign In or Register to access flights and bookings.', 'info');
    
    // Switch to home view where the login card is located
    if (this.activeTab !== 'home') {
      this.activeTab = 'home';
      document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active'));
      const homeBtn = document.getElementById('tab-btn-home');
      if (homeBtn) homeBtn.classList.add('active');

      document.querySelectorAll('.tab-view').forEach(view => {
        view.style.display = 'none';
        view.classList.remove('active');
      });
      const homeView = document.getElementById('view-home');
      if (homeView) {
        homeView.style.display = 'block';
        homeView.classList.add('active');
      }
    }

    this.highlightAuthCard();
  },

  highlightAuthCard() {
    const card = document.getElementById('home-auth-main-card');
    if (card) {
      card.classList.remove('auth-card-highlight');
      void card.offsetWidth; // trigger reflow
      card.classList.add('auth-card-highlight');
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });

      setTimeout(() => {
        card.classList.remove('auth-card-highlight');
        const emailInput = document.getElementById('home-auth-email');
        if (emailInput) emailInput.focus();
      }, 700);
    }
  },

  // =========================================================================
  // Homepage Embedded Auth Card
  // =========================================================================
  homeAuthMode: 'signin',

  setHomeAuthMode(mode) {
    this.homeAuthMode = mode;
    const signinTab = document.getElementById('home-tab-signin');
    const signupTab = document.getElementById('home-tab-signup');
    const title = document.getElementById('home-auth-title');
    const desc = document.getElementById('home-auth-desc');
    const btnText = document.getElementById('home-auth-btn-text');

    if (mode === 'signup') {
      signinTab?.classList.remove('active');
      signupTab?.classList.add('active');
      if (title) title.textContent = 'Register Mera Safar Account';
      if (desc) desc.textContent = 'Create your account for instant bookings and reservations.';
      if (btnText) btnText.textContent = 'Create Account & Enter';
    } else {
      signupTab?.classList.remove('active');
      signinTab?.classList.add('active');
      if (title) title.textContent = 'Welcome to Mera Safar';
      if (desc) desc.textContent = 'Sign in to manage bookings, reserve seats, or access operations.';
      if (btnText) btnText.textContent = 'Sign In to Mera Safar';
    }
  },

  fillDemoAccount(email, password) {
    const emailInput = document.getElementById('home-auth-email');
    const passInput = document.getElementById('home-auth-password');
    if (emailInput) emailInput.value = email;
    if (passInput) {
      passInput.value = password;
      passInput.focus();
    }
    this.showToast(`Auto-filled credentials for ${email}`, 'info');
  },

  togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
      input.type = 'text';
      btn.innerHTML = `<i class="fa-solid fa-eye-slash"></i>`;
    } else {
      input.type = 'password';
      btn.innerHTML = `<i class="fa-regular fa-eye"></i>`;
    }
  },

  async handleHomeAuthSubmit(e) {
    e.preventDefault();
    const email = document.getElementById('home-auth-email').value.trim();
    const password = document.getElementById('home-auth-password').value;
    const submitBtn = document.getElementById('btn-home-auth-submit');

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;

    try {
      if (this.homeAuthMode === 'signup') {
        const res = await api.signup(email, password);
        this.showToast(res.message || 'Account created successfully! Signing in...', 'success');
        await api.signin(email, password);
      } else {
        await api.signin(email, password);
        this.showToast('Signed in successfully! Entering Mera Safar Portal...', 'success');
      }

      this.setupAuthUI();
      // Advance to Flights view (or Operations console if ops/super_admin)!
      const currentUser = api.getCurrentUser();
      const role = (currentUser?.role || '').toLowerCase().replace('-', '_');
      setTimeout(() => {
        if (role === 'super_admin' || role === 'ops_agent') {
          this.switchTab('admin');
        } else {
          this.switchTab('search');
        }
      }, 500);
    } catch (err) {
      this.showToast(err.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<i class="fa-solid fa-right-to-bracket"></i> <span id="home-auth-btn-text">${this.homeAuthMode === 'signup' ? 'Create Account & Enter' : 'Sign In to Mera Safar'}</span>`;
    }
  },

  // =========================================================================
  // Flight Search & Listing
  // =========================================================================
  async loadAllFlights() {
    const grid = document.getElementById('flights-grid');
    grid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
        <i class="fa-solid fa-spinner fa-spin fa-2x"></i>
        <p style="margin-top: 12px;">Loading scheduled flights from database...</p>
      </div>
    `;

    try {
      const data = await api.getAllFlights();
      const flights = data.flights || [];
      this.flightsCache = flights;
      this.renderFlights(flights);

      document.getElementById('results-title').innerHTML = `
        <i class="fa-solid fa-plane-up"></i> Available Scheduled Flights
      `;
      document.getElementById('results-desc').textContent = 
        `Showing ${this.groupFlightsByNumber(flights).length} scheduled flights ready for instant booking`;
    } catch (err) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--accent-rose);">
          <i class="fa-solid fa-circle-exclamation fa-2x"></i>
          <p style="margin-top: 12px;">Failed to load flights: ${err.message}</p>
          <button class="btn btn-secondary btn-sm" onclick="app.loadAllFlights()" style="margin-top: 12px;">
            Retry
          </button>
        </div>
      `;
    }
  },

  groupFlightsByNumber(flights) {
    const grouped = {};
    flights.forEach(f => {
      const key = f.flight_number;
      if (!grouped[key]) {
        grouped[key] = {
          flight_id: f.flight_id,
          flight_number: f.flight_number,
          origin: f.origin,
          destination: f.destination,
          departure_time: f.departure_time,
          classes: {}
        };
      }
      grouped[key].classes[f.seat_class] = {
        available: f.available_seats,
        price: f.price
      };
    });
    return Object.values(grouped);
  },

  renderFlights(flightsList) {
    const grid = document.getElementById('flights-grid');
    const grouped = this.groupFlightsByNumber(flightsList);

    if (grouped.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px solid var(--border-subtle);">
          <i class="fa-solid fa-plane-slash fa-3x" style="color: var(--text-muted); margin-bottom: 16px;"></i>
          <h3>No Scheduled Flights Found</h3>
          <p style="color: var(--text-secondary); max-width: 440px; margin: 8px auto 20px;">
            No flights match your criteria. You can search different cities or browse all available flights.
          </p>
          <button class="btn btn-primary btn-sm" onclick="app.loadAllFlights()">
            Show All Flights
          </button>
        </div>
      `;
      return;
    }

    grid.innerHTML = grouped.map(flight => {
      const depDate = this.formatDate(flight.departure_time);
      const totalAvail = Object.values(flight.classes).reduce((acc, curr) => acc + (curr.available || 0), 0);
      const isSoldOut = totalAvail <= 0;

      const classRowsHtml = ['ECONOMY', 'BUSINESS', 'FIRST'].map(cls => {
        const info = flight.classes[cls];
        if (!info) return '';
        const avail = info.available || 0;
        const isSoldOutClass = avail <= 0;
        const badgeClass = avail > 10 ? 'seats-avail' : (avail > 0 ? 'seats-low' : 'seats-full');
        const badgeText = avail > 0 ? `${avail} Left` : 'Sold Out';
        const basePrice = info.price;
        const flexPrice = Math.round(basePrice * 1.30);

        return `
          <div class="class-row" style="flex-direction: column; align-items: stretch; gap: 6px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <div class="class-name">
                <i class="fa-solid fa-chair" style="color: var(--gold-400);"></i>
                <span>${cls}</span>
                <span class="seats-badge ${badgeClass}">${badgeText}</span>
              </div>
              <div style="text-align: right;">
                <div class="class-price">Rs. ${basePrice.toLocaleString()}</div>
                <div style="font-size: 10.5px; color: var(--text-muted);">Flex: Rs. ${flexPrice.toLocaleString()}</div>
              </div>
            </div>
            ${isSoldOutClass ? `
              <button class="btn btn-secondary btn-sm" style="width: 100%; justify-content: center;" onclick="app.openWaitlistModal('${flight.flight_number}', '${cls}')">
                <i class="fa-solid fa-user-clock"></i> Join ${cls} Waitlist
              </button>
            ` : ''}
          </div>
        `;
      }).join('');

      return `
        <div class="flight-card">
          <div class="flight-card-header">
            <div class="flight-num-badge">
              <i class="fa-solid fa-plane"></i>
              <span>${flight.flight_number}</span>
            </div>
            <span class="status-pill status-scheduled">
              <i class="fa-solid fa-circle" style="font-size: 8px;"></i> Scheduled
            </span>
          </div>

          <div class="route-visual">
            <div class="airport-node">
              <span class="airport-code">${flight.origin}</span>
              <span class="airport-city">Origin</span>
            </div>
            <div class="flight-path">
              <i class="fa-solid fa-plane plane-icon"></i>
              <div class="flight-line"></div>
              <span class="flight-time"><i class="fa-regular fa-clock"></i> ${depDate}</span>
            </div>
            <div class="airport-node" style="text-align: right;">
              <span class="airport-code">${flight.destination}</span>
              <span class="airport-city">Destination</span>
            </div>
          </div>

          <div class="classes-list">
            ${classRowsHtml}
          </div>

          <div class="flight-card-footer">
            ${isSoldOut ? `
              <button class="btn btn-secondary" style="flex: 1;" onclick="app.openWaitlistModal('${flight.flight_number}', 'ECONOMY')">
                <i class="fa-solid fa-clock"></i> Join Waitlist
              </button>
            ` : `
              <button class="btn btn-primary" style="flex: 1;" onclick="app.openBookingModal('${flight.flight_number}')">
                <i class="fa-solid fa-bolt"></i> Book Reservation
              </button>
            `}
          </div>
        </div>
      `;
    }).join('');
  },

  async handleSearchSubmit(e) {
    e.preventDefault();
    const origin = document.getElementById('search-origin').value.trim();
    const destination = document.getElementById('search-destination').value.trim();

    if (!origin || !destination) {
      this.showToast('Please enter both origin and destination', 'error');
      return;
    }

    const grid = document.getElementById('flights-grid');
    grid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
        <i class="fa-solid fa-spinner fa-spin fa-2x"></i>
        <p style="margin-top: 12px;">Searching flights for ${origin.toUpperCase()} → ${destination.toUpperCase()}...</p>
      </div>
    `;

    try {
      const res = await api.searchFlights(origin, destination);
      const flights = res.available_flights || [];
      this.renderFlights(flights);

      document.getElementById('results-title').innerHTML = `
        <i class="fa-solid fa-plane-up"></i> ${origin.toUpperCase()} → ${destination.toUpperCase()}
      `;
      document.getElementById('results-desc').textContent = 
        `Found ${this.groupFlightsByNumber(flights).length} scheduled flights with available seats`;
    } catch (err) {
      this.showToast(`Search error: ${err.message}`, 'error');
      this.loadAllFlights();
    }
  },

  swapSearchCities() {
    const orig = document.getElementById('search-origin');
    const dest = document.getElementById('search-destination');
    const temp = orig.value;
    orig.value = dest.value;
    dest.value = temp;
  },

  setSearchRoute(orig, dest) {
    document.getElementById('search-origin').value = orig;
    document.getElementById('search-destination').value = dest;
    document.getElementById('search-form').dispatchEvent(new Event('submit'));
  },

  // =========================================================================
  // Booking Modal & Checkout
  // =========================================================================
  async openBookingModal(flightNumber) {
    const flight = this.flightsCache.find(f => f.flight_number.toUpperCase() === flightNumber.toUpperCase());
    if (!flight) return;

    this.selectedFlightForBooking = flight;

    document.getElementById('book-flight-number').value = flight.flight_number;
    document.getElementById('modal-book-flight-title').textContent = `Flight ${flight.flight_number}`;
    document.getElementById('modal-book-route-subtitle').textContent = 
      `${flight.origin} → ${flight.destination} | ${this.formatDate(flight.departure_time)}`;

    const user = api.getCurrentUser();
    if (user && user.email) {
      document.getElementById('book-pass-email').value = user.email;
    }

    try {
      const priceData = await api.getFlightPrices(flight.flight_number);
      const pricing = priceData.pricing || [];
      this.currentPricesCache = {};

      pricing.forEach(p => {
        this.currentPricesCache[p.seat_class] = {
          price: p.price_per_seat,
          available: p.available_seats
        };

        const badge = document.getElementById(`badge-avail-${p.seat_class.toLowerCase()}`);
        const desc = document.getElementById(`price-desc-${p.seat_class.toLowerCase()}`);
        if (badge) {
          badge.textContent = `${p.available_seats} Left`;
          badge.className = `seats-badge ${p.available_seats > 0 ? 'seats-avail' : 'seats-full'}`;
        }
        if (desc) {
          desc.textContent = `Base: Rs. ${p.price_per_seat.toLocaleString()}`;
        }
      });

      const availClass = pricing.find(p => p.available_seats > 0)?.seat_class || 'ECONOMY';
      this.selectCabinClass(availClass);
    } catch (err) {
      console.warn('Could not fetch specific pricing:', err);
    }

    this.selectFareType('BASIC');
    this.setSeatCount(1);
    this.updateOrderSummary();

    this.openModal('modal-booking');
  },

  selectCabinClass(className) {
    document.getElementById('book-seat-class').value = className;

    const cards = document.querySelectorAll('#book-class-selector .radio-card');
    cards.forEach(card => card.classList.remove('selected'));

    const classNames = ['ECONOMY', 'BUSINESS', 'FIRST'];
    const idx = classNames.indexOf(className.toUpperCase());
    if (idx !== -1 && cards[idx]) {
      cards[idx].classList.add('selected');
    }

    const priceInfo = this.currentPricesCache[className.toUpperCase()];
    if (priceInfo) {
      document.getElementById('book-base-price').value = priceInfo.price;
    }

    this.updateOrderSummary();
  },

  selectFareType(fareType) {
    document.getElementById('book-fare-type').value = fareType;

    const basicCard = document.getElementById('fare-card-basic');
    const flexCard = document.getElementById('fare-card-flex');

    if (fareType === 'FLEX') {
      basicCard.classList.remove('selected');
      flexCard.classList.add('selected');
    } else {
      basicCard.classList.add('selected');
      flexCard.classList.remove('selected');
    }

    this.updateOrderSummary();
  },

  adjustSeatCount(delta) {
    let count = parseInt(document.getElementById('book-seat-count').value, 10) || 1;
    count = Math.max(1, Math.min(10, count + delta));
    this.setSeatCount(count);
  },

  setSeatCount(count) {
    document.getElementById('book-seat-count').value = count;
    document.getElementById('book-seat-count-display').textContent = count;
    this.renderAdditionalPassengers(count);
    this.updateOrderSummary();
  },

  renderAdditionalPassengers(count) {
    const container = document.getElementById('additional-passengers-container');
    if (count <= 1) {
      container.innerHTML = '';
      return;
    }

    let html = `
      <div style="margin-top: 14px; border-top: 1px solid var(--border-subtle); padding-top: 14px;">
        <label class="form-label" style="color: var(--gold-400);">Additional Co-Passengers (${count - 1})</label>
    `;

    for (let i = 2; i <= count; i++) {
      html += `
        <div class="form-row" style="margin-bottom: 10px;">
          <div>
            <input type="text" class="form-input additional-pass-name" placeholder="Passenger ${i} Full Name" required>
          </div>
          <div>
            <input type="email" class="form-input additional-pass-email" placeholder="Passenger ${i} Email" required>
          </div>
        </div>
      `;
    }

    html += `</div>`;
    container.innerHTML = html;
  },

  updateOrderSummary() {
    const basePrice = parseFloat(document.getElementById('book-base-price').value) || 0;
    const fareType = document.getElementById('book-fare-type').value;
    const seatCount = parseInt(document.getElementById('book-seat-count').value, 10) || 1;

    const multiplier = fareType === 'FLEX' ? 1.30 : 1.0;
    const pricePerSeat = Math.round(basePrice * multiplier);
    const totalFare = pricePerSeat * seatCount;

    document.getElementById('summary-base-price').textContent = `Rs. ${basePrice.toLocaleString()}`;
    document.getElementById('summary-fare-mult').textContent = fareType === 'FLEX' 
      ? '1.30x (Flex Fare — 100% Refundable)' 
      : '1.0x (Basic Fare — Non-Refundable)';
    document.getElementById('summary-seat-price').textContent = `Rs. ${pricePerSeat.toLocaleString()}`;
    document.getElementById('summary-seat-count').textContent = `x ${seatCount}`;
    document.getElementById('summary-total-fare').textContent = `Rs. ${totalFare.toLocaleString()}`;
  },

  async handleBookingSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-submit-booking');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing Transaction...`;

    const flightNumber = document.getElementById('book-flight-number').value;
    const seatClass = document.getElementById('book-seat-class').value;
    const fareType = document.getElementById('book-fare-type').value;
    const seatCount = parseInt(document.getElementById('book-seat-count').value, 10);

    const primaryName = document.getElementById('book-pass-name').value.trim();
    const primaryEmail = document.getElementById('book-pass-email').value.trim();

    const passengers = [
      { passenger_name: primaryName, passenger_email: primaryEmail }
    ];

    if (seatCount > 1) {
      const extraNames = document.querySelectorAll('.additional-pass-name');
      const extraEmails = document.querySelectorAll('.additional-pass-email');
      for (let i = 0; i < extraNames.length; i++) {
        passengers.push({
          passenger_name: extraNames[i].value.trim() || `Guest ${i + 2}`,
          passenger_email: extraEmails[i].value.trim() || `guest${i + 2}@pending.local`
        });
      }
    }

    const idempotencyKey = `idemp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const payload = {
      flight_number: flightNumber,
      seat_class: seatClass,
      fare_type: fareType,
      seat_count: seatCount,
      passengers: passengers
    };

    try {
      const res = await api.createBooking(payload, idempotencyKey);
      this.closeModal('modal-booking');
      this.showToast('Reservation successfully confirmed in database!', 'success');

      this.renderSuccessBoardingPass(res, primaryName, primaryEmail);
      this.openModal('modal-success');

      this.loadAllFlights();
    } catch (err) {
      this.showToast(`Booking Failed: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-lock"></i> Confirm & Book Reservation`;
    }
  },

  renderSuccessBoardingPass(bookingResult, name, email) {
    const container = document.getElementById('success-boarding-pass-preview');
    const bIds = bookingResult.booking_ids || [];
    const bIdDisplay = bIds.slice(0, 2).map(id => id.slice(0, 8).toUpperCase()).join(', ');

    container.innerHTML = `
      <div class="boarding-pass">
        <div class="pass-main">
          <div class="pass-header">
            <div class="brand-name" style="font-size: 18px;">
              <i class="fa-solid fa-plane-departure" style="color: var(--gold-400);"></i> Mera Safar
            </div>
            <span class="status-pill status-scheduled">
              <i class="fa-solid fa-check"></i> Confirmed
            </span>
          </div>

          <div class="pass-details-grid">
            <div class="detail-item">
              <span class="detail-label">Passenger</span>
              <span class="detail-val">${name}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Flight</span>
              <span class="detail-val pass-flight-code">${bookingResult.flight_number}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Class</span>
              <span class="detail-val">${bookingResult.seat_class}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Fare Protection</span>
              <span class="detail-val" style="color: ${bookingResult.fare_type === 'FLEX' ? 'var(--gold-400)' : 'var(--text-primary)'}">
                ${bookingResult.fare_type}
              </span>
            </div>
          </div>

          <div class="pass-details-grid" style="border-top: 1px dashed var(--border-subtle); padding-top: 10px;">
            <div class="detail-item">
              <span class="detail-label">Booking Reference</span>
              <span class="detail-val" style="font-family: monospace; font-size: 13px;">${bIdDisplay}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Seats Reserved</span>
              <span class="detail-val">${bookingResult.total_booked} Seat(s)</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Total Fare Paid</span>
              <span class="detail-val" style="color: var(--gold-400);">Rs. ${bookingResult.total_fare.toLocaleString()}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Refund Policy</span>
              <span class="detail-val" style="font-size: 11px; color: ${bookingResult.fare_type === 'FLEX' ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
                ${bookingResult.fare_note}
              </span>
            </div>
          </div>
        </div>

        <div class="pass-stub">
          <div style="font-size: 10.5px; color: var(--text-muted); font-weight: 700;">BOARDING PASS</div>
          <div style="margin: 12px 0;">
            <i class="fa-solid fa-qrcode fa-3x" style="color: var(--gold-400);"></i>
          </div>
          <div class="barcode-strip">||||||||||||||||</div>
          <div style="font-size: 10px; color: var(--text-secondary);">${bookingResult.flight_number} • ${bookingResult.seat_class}</div>
        </div>
      </div>
    `;
  },

  printBoardingPass() {
    window.print();
  },

  // =========================================================================
  // My Bookings & Boarding Pass Lookup
  // =========================================================================
  async handleLookupBookings(e) {
    e.preventDefault();
    const email = document.getElementById('lookup-email').value.trim();
    if (!email) return;
    this.lookupBookingsForEmail(email);
  },

  async lookupBookingsForEmail(email) {
    const container = document.getElementById('my-bookings-container');
    container.innerHTML = `
      <div style="text-align: center; padding: 40px; color: var(--text-muted);">
        <i class="fa-solid fa-spinner fa-spin fa-2x"></i>
        <p style="margin-top: 12px;">Searching bookings for ${email}...</p>
      </div>
    `;

    try {
      const res = await api.getPassengerBookings(email);
      const bookings = res.bookings || [];
      this.renderPassengerBookings(bookings, email);
    } catch (err) {
      container.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--accent-rose);">
          <i class="fa-solid fa-circle-exclamation fa-2x"></i>
          <p style="margin-top: 12px;">Error fetching bookings: ${err.message}</p>
        </div>
      `;
    }
  },

  renderPassengerBookings(bookings, email) {
    const container = document.getElementById('my-bookings-container');

    if (bookings.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 60px 20px; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px solid var(--border-subtle);">
          <i class="fa-solid fa-plane-slash fa-3x" style="color: var(--text-muted); margin-bottom: 16px;"></i>
          <h3>No Bookings Found</h3>
          <p style="color: var(--text-secondary); max-width: 440px; margin: 8px auto 20px;">
            No tickets found for "${email}". Make a new reservation to view boarding passes here.
          </p>
          <button class="btn btn-primary btn-sm" onclick="app.switchTab('search')">
            Browse & Book Flights
          </button>
        </div>
      `;
      return;
    }

    const confirmedCount = bookings.filter(b => b.status === 'CONFIRMED').length;
    const cancelledCount = bookings.filter(b => b.status === 'CANCELLED').length;

    let html = `
      <div style="display: flex; gap: 16px; margin-bottom: 24px;">
        <div class="user-pill">
          <span>Total Bookings: <strong>${bookings.length}</strong></span>
        </div>
        <div class="user-pill">
          <span style="color: var(--accent-emerald);">Confirmed: <strong>${confirmedCount}</strong></span>
        </div>
        <div class="user-pill">
          <span style="color: var(--text-muted);">Cancelled: <strong>${cancelledCount}</strong></span>
        </div>
      </div>
      <div class="tickets-grid">
    `;

    bookings.forEach(b => {
      const isConfirmed = b.status === 'CONFIRMED';
      const statusBadge = isConfirmed 
        ? `<span class="status-pill status-scheduled"><i class="fa-solid fa-check"></i> Confirmed</span>`
        : `<span class="status-pill status-cancelled"><i class="fa-solid fa-ban"></i> Cancelled</span>`;

      const fareBadge = b.fare_type === 'FLEX'
        ? `<span class="fare-tag tag-flex" style="font-size: 11px;">FLEX (100% Refundable)</span>`
        : `<span class="fare-tag tag-basic" style="font-size: 11px;">BASIC (Non-refundable)</span>`;

      html += `
        <div class="boarding-pass">
          <div class="pass-main">
            <div class="pass-header">
              <div class="brand-name" style="font-size: 18px;">
                <i class="fa-solid fa-plane-departure" style="color: var(--gold-400);"></i> Mera Safar
              </div>
              <div>${statusBadge}</div>
            </div>

            <div class="route-visual" style="margin: 6px 0;">
              <div class="airport-node">
                <span class="airport-code" style="font-size: 22px;">${b.origin}</span>
              </div>
              <div class="flight-path">
                <i class="fa-solid fa-plane plane-icon"></i>
                <div class="flight-line"></div>
                <span class="flight-time">${this.formatDate(b.departure_time)}</span>
              </div>
              <div class="airport-node" style="text-align: right;">
                <span class="airport-code" style="font-size: 22px;">${b.destination}</span>
              </div>
            </div>

            <div class="pass-details-grid">
              <div class="detail-item">
                <span class="detail-label">Passenger</span>
                <span class="detail-val">${b.passenger_name}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Flight</span>
                <span class="detail-val pass-flight-code">${b.flight_number}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Cabin Class</span>
                <span class="detail-val">${b.seat_class}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Fare Protection</span>
                <div>${fareBadge}</div>
              </div>
            </div>

            <div class="pass-details-grid" style="border-top: 1px dashed var(--border-subtle); padding-top: 10px; align-items: center;">
              <div class="detail-item">
                <span class="detail-label">Ticket ID</span>
                <span class="detail-val" style="font-family: monospace; font-size: 12px;">${b.booking_id.slice(0, 8).toUpperCase()}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Price Paid</span>
                <span class="detail-val" style="color: var(--gold-400);">Rs. ${b.price_paid.toLocaleString()}</span>
              </div>
              <div class="detail-item" style="grid-column: span 2; text-align: right;">
                ${isConfirmed ? `
                  <button class="btn btn-danger btn-sm" onclick="app.openCancelModal('${b.flight_number}', '${b.seat_class}', '${b.passenger_email}', ${b.price_paid}, '${b.fare_type}')">
                    <i class="fa-solid fa-ban"></i> Cancel Ticket & Refund
                  </button>
                ` : `
                  <span style="font-size: 12px; color: var(--text-muted);">Cancelled on record</span>
                `}
              </div>
            </div>
          </div>

          <div class="pass-stub">
            <div style="font-size: 10.5px; color: var(--text-muted); font-weight: 700;">BOARDING PASS</div>
            <div style="margin: 10px 0;">
              <i class="fa-solid fa-qrcode fa-3x" style="color: var(--gold-400);"></i>
            </div>
            <div class="barcode-strip">||||||||||||||||</div>
            <div style="font-size: 10px; color: var(--text-secondary);">${b.flight_number} • ${b.seat_class}</div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  },

  // =========================================================================
  // Cancellation Modal & Live Refund Calculator
  // =========================================================================
  openCancelModal(flightNumber, seatClass, email, pricePaid, fareType) {
    document.getElementById('cancel-flight-number').value = flightNumber;
    document.getElementById('cancel-seat-class').value = seatClass;
    document.getElementById('cancel-email').value = email;
    document.getElementById('cancel-base-price').value = pricePaid;

    document.getElementById('cancel-flight-info').textContent = 
      `Flight ${flightNumber} • Class: ${seatClass}`;
    document.getElementById('cancel-display-email').textContent = email;
    document.getElementById('cancel-display-class').textContent = seatClass;

    this.setCancelSeatCount(1);

    const fareSelect = document.getElementById('cancel-fare-type-select');
    fareSelect.value = fareType || '';

    this.calculateRefundPreview();
    this.openModal('modal-cancel');
  },

  adjustCancelSeatCount(delta) {
    let count = parseInt(document.getElementById('cancel-seats-to-cancel').value, 10) || 1;
    count = Math.max(1, Math.min(10, count + delta));
    this.setCancelSeatCount(count);
  },

  setCancelSeatCount(count) {
    document.getElementById('cancel-seats-to-cancel').value = count;
    document.getElementById('cancel-seats-count-display').textContent = count;
    this.calculateRefundPreview();
  },

  calculateRefundPreview() {
    const count = parseInt(document.getElementById('cancel-seats-to-cancel').value, 10) || 1;
    const pricePaid = parseFloat(document.getElementById('cancel-base-price').value) || 0;
    const selectedFareType = document.getElementById('cancel-fare-type-select').value;

    let flexRefund = pricePaid * count;
    let expectedNet = 0;
    if (selectedFareType === 'FLEX') {
      expectedNet = flexRefund;
    } else if (selectedFareType === 'BASIC') {
      expectedNet = 0;
    } else {
      expectedNet = flexRefund;
    }

    document.getElementById('refund-preview-flex').textContent = 
      `Rs. ${flexRefund.toLocaleString()} (100% Full Refund)`;
    document.getElementById('refund-preview-basic').textContent = 
      `Rs. 0 (Non-refundable)`;
    document.getElementById('refund-preview-total').textContent = 
      `Rs. ${expectedNet.toLocaleString()} ${selectedFareType === 'BASIC' ? '(No Refund)' : '(Refundable)'}`;
  },

  async handleCancelSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-submit-cancel');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing Cancellation...`;

    const flightNumber = document.getElementById('cancel-flight-number').value;
    const seatClass = document.getElementById('cancel-seat-class').value;
    const email = document.getElementById('cancel-email').value;
    const seatsToCancel = parseInt(document.getElementById('cancel-seats-to-cancel').value, 10);
    const fareType = document.getElementById('cancel-fare-type-select').value || null;

    const payload = {
      flight_number: flightNumber,
      passenger_email: email,
      seat_class: seatClass,
      seats_to_cancel: seatsToCancel
    };

    if (fareType) {
      payload.fare_type = fareType;
    }

    try {
      const res = await api.cancelBooking(payload);
      this.closeModal('modal-cancel');

      const refundAmount = res.refund?.total_refund_amount || 0;
      const remainingSeats = res.remaining_confirmed_seats?.total || 0;

      this.showToast(
        `Cancelled ${res.seats_cancelled} seat(s)! Refund: Rs. ${refundAmount.toLocaleString()}. Remaining: ${remainingSeats} seat(s).`,
        'success'
      );

      this.lookupBookingsForEmail(email);
      this.loadAllFlights();
    } catch (err) {
      this.showToast(`Cancellation failed: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-ban"></i> Confirm Cancellation & Process Refund`;
    }
  },

  // =========================================================================
  // Waitlist Modal
  // =========================================================================
  openWaitlistModal(flightNumber, seatClass = 'ECONOMY') {
    document.getElementById('waitlist-flight-number').value = flightNumber;
    document.getElementById('waitlist-seat-class').value = seatClass;
    document.getElementById('waitlist-flight-info').textContent = 
      `Flight ${flightNumber} • Class: ${seatClass} (Full)`;

    const user = api.getCurrentUser();
    if (user && user.email) {
      document.getElementById('waitlist-email').value = user.email;
    }

    this.openModal('modal-waitlist');
  },

  async handleWaitlistSubmit(e) {
    e.preventDefault();
    const flightNumber = document.getElementById('waitlist-flight-number').value;
    const seatClass = document.getElementById('waitlist-seat-class').value;
    const email = document.getElementById('waitlist-email').value.trim();
    const priority = parseInt(document.getElementById('waitlist-priority').value, 10) || 1;

    try {
      await api.joinWaitlist({
        flight_number: flightNumber,
        seat_class: seatClass,
        passenger_email: email,
        priority: priority
      });

      this.closeModal('modal-waitlist');
      this.showToast(`Joined waitlist for ${flightNumber} (${seatClass})!`, 'success');
    } catch (err) {
      this.showToast(`Waitlist error: ${err.message}`, 'error');
    }
  },

  // =========================================================================
  // Admin & Operations Console (Role-Sensitive)
  // =========================================================================
  async loadAdminFlights() {
    const tbody = document.getElementById('admin-flights-tbody');
    const roleBanner = document.getElementById('admin-role-banner');
    const topCreateBtn = document.getElementById('btn-create-flight-top');

    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 40px; color: var(--text-muted);">
          <i class="fa-solid fa-spinner fa-spin fa-2x"></i>
          <p style="margin-top: 12px;">Loading flight inventory & audit records...</p>
        </td>
      </tr>
    `;

    try {
      const res = await api.getAdminFlights();
      const flights = res.flights || [];
      const role = (res.role || api.getCurrentUser()?.role || 'ops_agent').toLowerCase().replace('-', '_');
      const email = res.admin_email || api.getCurrentUser()?.email || '';

      const curr = api.getCurrentUser();
      if (curr && curr.role !== role) {
        api.setCurrentUser({ ...curr, role });
        this.setupAuthUI();
      }

      // Render live role banner
      if (roleBanner) {
        if (role === 'ops_agent') {
          roleBanner.innerHTML = `
            <div style="padding: 14px 20px; border-radius: var(--radius-md); background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
              <div style="display: flex; align-items: center; gap: 12px;">
                <span class="user-role-badge role-ops_agent" style="font-size: 12px; padding: 4px 10px;">
                  <i class="fa-solid fa-user-gear"></i> OPS AGENT PORTAL
                </span>
                <span style="font-size: 13.5px; color: var(--text-primary);">
                  Welcome <strong>${email}</strong>! Authorized operations: <strong>Flight Schedule Rescheduling</strong> and <strong>Inventory Monitoring</strong>.
                </span>
              </div>
              <div style="font-size: 12px; color: #7dd3fc; font-weight: 600;">
                <i class="fa-solid fa-circle-check" style="color: var(--accent-emerald);"></i> Operational Privileges Active
              </div>
            </div>
          `;
          if (topCreateBtn) {
            topCreateBtn.style.display = 'none'; // Hidden for ops_agent
          }
        } else if (role === 'super_admin') {
          roleBanner.innerHTML = `
            <div style="padding: 14px 20px; border-radius: var(--radius-md); background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.3); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
              <div style="display: flex; align-items: center; gap: 12px;">
                <span class="user-role-badge role-super_admin" style="font-size: 12px; padding: 4px 10px;">
                  <i class="fa-solid fa-crown"></i> SUPER ADMIN
                </span>
                <span style="font-size: 13.5px; color: var(--text-primary);">
                  Welcome <strong>${email}</strong>! Master rights: <strong>Flight Creation</strong>, <strong>Rescheduling</strong>, and <strong>Emergency Cancellation</strong>.
                </span>
              </div>
              <div style="font-size: 12px; color: #fda4af; font-weight: 600;">
                <i class="fa-solid fa-shield"></i> Master Administrative Access
              </div>
            </div>
          `;
          if (topCreateBtn) {
            topCreateBtn.style.display = 'inline-flex';
            topCreateBtn.disabled = false;
            topCreateBtn.style.opacity = '1';
            topCreateBtn.style.cursor = 'pointer';
            topCreateBtn.title = 'Schedule a new flight';
            topCreateBtn.innerHTML = `<i class="fa-solid fa-plus"></i> Create New Flight`;
          }
        }
      }

      this.renderAdminFlightsTable(flights, role);
    } catch (err) {
      if (roleBanner) roleBanner.innerHTML = '';
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 40px; color: var(--accent-rose);">
            <i class="fa-solid fa-lock fa-2x"></i>
            <p style="margin-top: 12px; font-weight: bold;">Super-Admin or Ops-Agent authentication required</p>
            <p style="font-size: 13px; color: var(--text-secondary); max-width: 480px; margin: 4px auto 16px;">
              ${err.message}. Please sign in with an ops_agent or super_admin account.
            </p>
            <button class="btn btn-primary btn-sm" onclick="app.openAuthModal('signin')">
              Sign In
            </button>
          </td>
        </tr>
      `;
    }
  },

  renderAdminFlightsTable(flights, role = 'ops_agent') {
    const tbody = document.getElementById('admin-flights-tbody');
    if (flights.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 30px; color: var(--text-muted);">
            No flights found in database.
          </td>
        </tr>
      `;
      return;
    }

    const isOps = role === 'ops_agent';

    tbody.innerHTML = flights.map(f => {
      const isScheduled = f.status === 'SCHEDULED';
      const statusBadge = isScheduled
        ? `<span class="status-pill status-scheduled">Scheduled</span>`
        : `<span class="status-pill status-cancelled">Cancelled</span>`;

      const classesSummary = (f.classes || []).map(c => 
        `<span class="seats-badge ${c.available_seats > 0 ? 'seats-avail' : 'seats-full'}" style="margin: 2px;">
          ${c.seat_class}: ${c.booked_seats}/${c.total_seats} (Rs. ${c.price})
        </span>`
      ).join(' ');

      let actionButtons = '';
      if (isScheduled) {
        if (isOps) {
          actionButtons = `
            <button class="btn btn-primary btn-sm" onclick="app.openUpdateScheduleModal('${f.flight_number}', '${f.departure_time}')" title="Update Departure Schedule">
              <i class="fa-solid fa-clock"></i> Reschedule
            </button>
          `;
        } else {
          actionButtons = `
            <button class="btn btn-secondary btn-sm" onclick="app.openUpdateScheduleModal('${f.flight_number}', '${f.departure_time}')" title="Update Departure Schedule">
              <i class="fa-solid fa-clock"></i> Reschedule
            </button>
            <button class="btn btn-danger btn-sm" onclick="app.confirmCancelFlight('${f.flight_number}')" title="Emergency Cancel">
              <i class="fa-solid fa-ban"></i> Cancel
            </button>
          `;
        }
      } else {
        actionButtons = `<span style="font-size: 12px; color: var(--text-muted);">Cancelled</span>`;
      }

      return `
        <tr>
          <td><strong style="color: var(--gold-400);">${f.flight_number}</strong></td>
          <td><strong>${f.origin}</strong> → <strong>${f.destination}</strong></td>
          <td>${this.formatDate(f.departure_time)}</td>
          <td>${f.total_capacity}</td>
          <td>${classesSummary || '--'}</td>
          <td>${statusBadge}</td>
          <td>
            <div style="display: flex; gap: 8px;">
              ${actionButtons}
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  openCreateFlightModal() {
    const userRole = (api.getCurrentUser()?.role || '').toLowerCase().replace('-', '_');
    if (userRole === 'ops_agent') {
      this.showToast('Access Denied: Sirf Super-Admin nayi flight schedule kar sakta hai.', 'error');
      return;
    }
    this.openModal('modal-create-flight');
    this.validateCapacitySum();
  },

  validateCapacitySum() {
    const cap = parseInt(document.getElementById('admin-new-capacity').value, 10) || 0;
    const eco = parseInt(document.getElementById('seat-cnt-eco').value, 10) || 0;
    const bus = parseInt(document.getElementById('seat-cnt-bus').value, 10) || 0;
    const fst = parseInt(document.getElementById('seat-cnt-fst').value, 10) || 0;

    const sum = eco + bus + fst;
    const warning = document.getElementById('capacity-sum-warning');
    const submitBtn = document.getElementById('btn-create-flight-submit');

    if (sum === cap) {
      warning.style.color = 'var(--accent-emerald)';
      warning.textContent = `Seats: ${eco} + ${bus} + ${fst} = ${sum} (Matches Capacity: ${cap})`;
      submitBtn.disabled = false;
    } else {
      warning.style.color = 'var(--accent-rose)';
      warning.textContent = `Seats sum (${sum}) does not match Total Capacity (${cap})! Difference: ${cap - sum}`;
      submitBtn.disabled = true;
    }
  },

  async handleCreateFlightSubmit(e) {
    e.preventDefault();
    const flightNum = document.getElementById('admin-new-flight-num').value.trim();
    const origin = document.getElementById('admin-new-origin').value.trim();
    const dest = document.getElementById('admin-new-dest').value.trim();
    const depTime = document.getElementById('admin-new-dep-time').value;
    const cap = parseInt(document.getElementById('admin-new-capacity').value, 10);

    const seats = {
      ECONOMY: parseInt(document.getElementById('seat-cnt-eco').value, 10),
      BUSINESS: parseInt(document.getElementById('seat-cnt-bus').value, 10),
      FIRST: parseInt(document.getElementById('seat-cnt-fst').value, 10)
    };

    const prices = {
      ECONOMY: parseFloat(document.getElementById('price-eco').value),
      BUSINESS: parseFloat(document.getElementById('price-bus').value),
      FIRST: parseFloat(document.getElementById('price-fst').value)
    };

    const payload = {
      flight_number: flightNum,
      origin: origin,
      destination: dest,
      departure_time: new Date(depTime).toISOString(),
      total_capacity: cap,
      seats: seats,
      prices: prices
    };

    try {
      await api.createFlight(payload);
      this.closeModal('modal-create-flight');
      this.showToast(`Flight ${flightNum.toUpperCase()} successfully scheduled!`, 'success');
      this.loadAdminFlights();
      this.loadAllFlights();
    } catch (err) {
      this.showToast(`Create flight error: ${err.message}`, 'error');
    }
  },

  openUpdateScheduleModal(flightNumber, currentDepTime) {
    document.getElementById('update-schedule-flight-num').value = flightNumber;
    document.getElementById('update-schedule-flight-title').textContent = `Flight ${flightNumber}`;

    if (currentDepTime) {
      try {
        const d = new Date(currentDepTime);
        document.getElementById('update-new-dep-time').value = d.toISOString().slice(0, 16);
      } catch (e) {}
    }

    this.openModal('modal-update-schedule');
  },

  async handleUpdateScheduleSubmit(e) {
    e.preventDefault();
    const flightNumber = document.getElementById('update-schedule-flight-num').value;
    const newDepTime = document.getElementById('update-new-dep-time').value;

    try {
      await api.updateFlightSchedule(flightNumber, new Date(newDepTime).toISOString());
      this.closeModal('modal-update-schedule');
      this.showToast(`Schedule updated for ${flightNumber}!`, 'success');
      this.loadAdminFlights();
      this.loadAllFlights();
    } catch (err) {
      this.showToast(`Update schedule error: ${err.message}`, 'error');
    }
  },

  async confirmCancelFlight(flightNumber) {
    const userRole = (api.getCurrentUser()?.role || '').toLowerCase().replace('-', '_');
    if (userRole === 'ops_agent') {
      this.showToast('Access Denied: Sirf Super-Admin flight cancel kar sakta hai.', 'error');
      return;
    }

    if (!confirm(`Are you sure you want to CANCEL Flight ${flightNumber}? This will automatically cancel all confirmed bookings and unlock customer refunds.`)) {
      return;
    }

    try {
      await api.cancelAdminFlight(flightNumber);
      this.showToast(`Flight ${flightNumber} has been cancelled.`, 'success');
      this.loadAdminFlights();
      this.loadAllFlights();
    } catch (err) {
      this.showToast(`Cancel error: ${err.message}`, 'error');
    }
  },

  // =========================================================================
  // Authentication UI & State
  // =========================================================================
  setupAuthUI() {
    const user = api.getCurrentUser();
    const container = document.getElementById('nav-auth-container');
    const adminTabBtn = document.getElementById('tab-btn-admin');
    const homeAuthCard = document.getElementById('home-auth-main-card');

    if (user && user.email) {
      const initial = user.email.charAt(0).toUpperCase();
      const role = (user.role || 'user').toLowerCase().replace('-', '_');
      const roleClass = `role-${role}`;
      const roleLabel = role.replace('_', ' ').toUpperCase();
      const isPrivileged = role === 'super_admin' || role === 'ops_agent';

      container.innerHTML = `
        <div class="user-pill">
          <div class="user-avatar">${initial}</div>
          <span style="font-size: 13px; font-weight: 600;">${user.email}</span>
          <span class="user-role-badge ${roleClass}">${roleLabel}</span>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="app.handleSignout()">
          <i class="fa-solid fa-right-from-bracket"></i> Sign Out
        </button>
      `;

      // Show Operations tab only for super_admin and ops_agent
      if (adminTabBtn) adminTabBtn.style.display = isPrivileged ? '' : 'none';

      // Hide login/signup card when already logged in
      if (homeAuthCard) homeAuthCard.style.display = 'none';

    } else {
      container.innerHTML = `
        <button class="btn btn-secondary btn-sm" onclick="app.openAuthModal('signin')">
          <i class="fa-solid fa-right-to-bracket"></i> Sign In
        </button>
        <button class="btn btn-primary btn-sm" onclick="app.openAuthModal('signup')">
          Sign Up
        </button>
      `;

      // Show Operations tab button again (it won't be accessible without login anyway)
      if (adminTabBtn) adminTabBtn.style.display = 'none'; // hide for non-logged-in users too

      // Show login/signup card for guests
      if (homeAuthCard) homeAuthCard.style.display = '';
    }
  },

  openAuthModal(mode = 'signin') {
    document.getElementById('auth-mode').value = mode;
    const title = document.getElementById('auth-modal-title');
    const subtitle = document.getElementById('auth-modal-subtitle');
    const submitBtn = document.getElementById('auth-submit-btn');
    const togglePrompt = document.getElementById('auth-toggle-prompt');
    const toggleLink = document.getElementById('auth-toggle-link');

    if (mode === 'signup') {
      title.textContent = 'Create Mera Safar Account';
      subtitle.textContent = 'Register for instant bookings and priority reservations';
      submitBtn.textContent = 'Create Account';
      togglePrompt.textContent = 'Already have an account?';
      toggleLink.textContent = 'Sign In';
    } else {
      title.textContent = 'Sign In to Mera Safar';
      subtitle.textContent = 'Access your reservations and manage bookings';
      submitBtn.textContent = 'Sign In';
      togglePrompt.textContent = "Don't have an account?";
      toggleLink.textContent = 'Create Account';
    }

    this.openModal('modal-auth');
  },

  toggleAuthMode() {
    const currentMode = document.getElementById('auth-mode').value;
    this.openAuthModal(currentMode === 'signin' ? 'signup' : 'signin');
  },

  async handleAuthSubmit(e) {
    e.preventDefault();
    const mode = document.getElementById('auth-mode').value;
    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value;

    const btn = document.getElementById('auth-submit-btn');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Please wait...`;

    try {
      if (mode === 'signup') {
        const res = await api.signup(email, password);
        this.showToast(res.message || 'Account created successfully! Now signing in...', 'success');
        await api.signin(email, password);
      } else {
        await api.signin(email, password);
        this.showToast('Signed in successfully!', 'success');
      }

      this.closeModal('modal-auth');
      this.setupAuthUI();

      const user = api.getCurrentUser();
      const role = (user?.role || '').toLowerCase().replace('-', '_');
      if (role === 'super_admin' || role === 'ops_agent') {
        this.switchTab('admin');
      } else {
        this.switchTab('search');
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = mode === 'signup' ? 'Create Account' : 'Sign In';
    }
  },

  handleSignout() {
    api.signout();
    this.setupAuthUI();
    this.showToast('Signed out successfully. Authentication is required to access the portal.', 'info');
    this.switchTab('home');
  },

  // =========================================================================
  // Modal Utilities
  // =========================================================================
  openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  },

  closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    }
  },

  // =========================================================================
  // Toast Notifications
  // =========================================================================
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = type === 'success' 
      ? '<i class="fa-solid fa-circle-check" style="color: var(--accent-emerald);"></i>' 
      : type === 'error' 
      ? '<i class="fa-solid fa-circle-exclamation" style="color: var(--accent-rose);"></i>' 
      : '<i class="fa-solid fa-circle-info" style="color: var(--accent-cyan);"></i>';

    toast.innerHTML = `
      ${icon}
      <span style="flex: 1;">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  },

  formatDate(dateStr) {
    if (!dateStr) return '--';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  }
};

// Initialize Application on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  app.init();

  // Close modal when pressing Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(m => {
        app.closeModal(m.id);
      });
    }
  });

  // Close modal when clicking outside (on overlay backdrop)
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
      app.closeModal(e.target.id);
    }
  });
});
