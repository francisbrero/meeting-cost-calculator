/***** CONFIG *****/
var CONFIG = {
    SHEET_ID: SpreadsheetApp.getActive().getId(), // Or paste the ID explicitly
    SHEET_OUTPUT: 'Output_Events',
    SHEET_RATES: 'Rates',
    DOMAIN: 'madkudu.com',            // <-- your Google Workspace domain
    LOOKBACK_DAYS: 30,                   // how far back to fetch
    LOOKAHEAD_DAYS: 3,                  // how far forward to fetch (recurring series, planning)
    DEFAULT_RATE: 125,                   // fallback hourly rate if no match
    MAX_USERS: 1000,                    // safety for large domains
    BATCH_SLEEP_MS: 50,                  // small pause between API calls
    ONLY_COUNT_ACCEPTED: false           // if true, exclude "declined" attendees
  };
  
    /***** ENTRY POINT *****/
  function daily_meeting_cost_snapshot() {
    var ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
    var output = ensureOutputHeader(ss.getSheetByName(CONFIG.SHEET_OUTPUT) || ss.insertSheet(CONFIG.SHEET_OUTPUT));
    var rates = loadRates(ss.getSheetByName(CONFIG.SHEET_RATES));
    var now = new Date();
    var timeMin = isoDate(addDays(now, -CONFIG.LOOKBACK_DAYS));
    var timeMax = isoDate(addDays(now, CONFIG.LOOKAHEAD_DAYS));

    var users = listActiveUsers(CONFIG.MAX_USERS);
    var rateCache = {};   // email -> {title, department}
    var processedMeetings = {}; // event_id + instance_start -> meeting data
    var rows = [];

    for (var i = 0; i < users.length; i++) {
      if (i % 25 === 0) Utilities.sleep(CONFIG.BATCH_SLEEP_MS);
      var u = users[i];
      var calendarId = u.primaryEmail;
      var events = listEvents(calendarId, timeMin, timeMax);

      for (var j = 0; j < events.length; j++) {
        var ev = events[j];
        var attendees = (ev.attendees || []).filter(function(a){ return a && a.email; });

        var filtered = CONFIG.ONLY_COUNT_ACCEPTED
          ? attendees.filter(function(a){ return String(a.responseStatus || '').toLowerCase() !== 'declined'; })
          : attendees;

        // Internal-only / internal attendees
        var internalAttendees = filtered.filter(function(a){ return isInternal(a.email); });
        if (internalAttendees.length === 0) continue; // skip meetings with no internal attendees

        // Duration (skip all-day)
        var dur = getDuration(ev);
        if (dur.durationHours <= 0) continue;

        // Create unique meeting key
        var meetingKey = ev.id + '|' + dur.startIso;
        
        // Skip if we've already processed this meeting
        if (processedMeetings[meetingKey]) continue;
        
        // Mark as processed
        processedMeetings[meetingKey] = true;

        // Organizer info
        var orgEmail = (ev.organizer && ev.organizer.email) || calendarId;
        var orgProfile = getProfile(orgEmail, rateCache);
        var organizerDept = orgProfile && orgProfile.department ? orgProfile.department : '';
        var organizerTitle = orgProfile && orgProfile.title ? orgProfile.title : '';

        // Attendee profiles & rates
        var attendeeProfiles = internalAttendees.map(function(a){
          var p = getProfile(a.email, rateCache);
          var rate = mapRate(p, rates);
          return {
            email: a.email,
            title: (p && p.title) ? p.title : '',
            dept:  (p && p.department) ? p.department : '',
            rate:  rate
          };
        });

        // Calculate total meeting cost
        var totalCost = 0;
        for (var k = 0; k < attendeeProfiles.length; k++) {
          var r = attendeeProfiles[k].rate;
          totalCost += Math.round(dur.durationHours * (r != null ? r : CONFIG.DEFAULT_RATE));
        }

        var eventDate = dur.startIso.slice(0, 10);
        var weekStart = getWeekStart(new Date(dur.startIso));
        var internalOnly = internalAttendees.length === filtered.length;

        // Create one row per meeting
        rows.push([
          eventDate,
          weekStart,
          orgEmail,
          organizerDept,
          organizerTitle,
          orgEmail, // calendar_id = organizer email
          ev.id,
          dur.startIso,
          dur.endIso,
          Number(dur.durationHours.toFixed(2)),
          filtered.length,
          internalAttendees.length,
          internalOnly,
          ev.recurringEventId || '',
          attendeeProfiles.map(function(x){ return x.email; }).join(';'),
          attendeeProfiles.map(function(x){ return x.title; }).join(';'),
          attendeeProfiles.map(function(x){ return x.dept;  }).join(';'),
          totalCost
        ]);
      }
    }

    // Write rows; de-duplicate by (calendar_id, event_id, instance_start)
    upsertRows(output, rows, ['calendar_id','event_id','instance_start']);
  }
  
  /***** ADMIN DIRECTORY HELPERS *****/
  function listActiveUsers(max) {
    var users = [];
    var pageToken;
    do {
      var resp = AdminDirectory.Users.list({
        customer: 'my_customer',
        maxResults: 500,
        orderBy: 'email',
        query: 'isSuspended=false',
        pageToken: pageToken
      });
      (resp.users || []).forEach(function(u){ users.push(u); });
      pageToken = resp.nextPageToken;
    } while (pageToken && users.length < max);
    return users.slice(0, max);
  }
  
  function getProfile(email, cache) {
    if (cache[email]) return cache[email];
    try {
      var u = AdminDirectory.Users.get(email, { projection: 'full' });
      var title = (u.organizations && u.organizations[0] && u.organizations[0].title) || '';
      var department = (u.organizations && u.organizations[0] && u.organizations[0].department) || '';
      cache[email] = { title: title, department: department };
    } catch (e) {
      cache[email] = { title: '', department: '' };
    }
    return cache[email];
  }
  
  /***** CALENDAR HELPERS *****/
  function listEvents(calendarId, timeMin, timeMax) {
    var events = [];
    var pageToken;
    do {
      var resp = Calendar.Events.list(calendarId, {
        timeMin: timeMin,
        timeMax: timeMax,
        showDeleted: false,
        singleEvents: true, // expand recurrences
        maxResults: 2500,
        pageToken: pageToken,
        fields: 'items(attendees,organizer,id,recurringEventId,start,end,summary,updated),nextPageToken'
      });
      (resp.items || []).forEach(function(e){ events.push(e); });
      pageToken = resp.nextPageToken;
    } while (pageToken);
    return events;
  }
  
  /***** RATE MAPPING *****/
  function loadRates(sheet) {
    if (!sheet) throw new Error('Missing Rates sheet');
    var values = sheet.getDataRange().getValues();
    var header = values.shift().map(function(h){ return String(h).trim().toLowerCase(); });
    var idxTitle = header.indexOf('title_regex');
    var idxDept  = header.indexOf('dept_regex');
    var idxRate  = header.indexOf('hourly_loaded_rate');
  
    var out = [];
    for (var i = 0; i < values.length; i++) {
      var r = values[i];
      if (r[idxRate] === '') continue;
      out.push({
        titleRe: safeRegex(r[idxTitle]),
        deptRe:  safeRegex(r[idxDept]),
        rate: Number(r[idxRate])
      });
    }
    return out;
  }
  
  function mapRate(profile, rates) {
    var title = (profile && profile.title) ? String(profile.title).trim() : '';
    var dept  = (profile && profile.department) ? String(profile.department).trim() : '';
  
    for (var i = 0; i < rates.length; i++) {
      var r = rates[i];
      if (r.titleRe && title && r.titleRe.test(title)) return r.rate;
    }
    for (var j = 0; j < rates.length; j++) {
      var r2 = rates[j];
      if (r2.deptRe && dept && r2.deptRe.test(dept)) return r2.rate;
    }
    return CONFIG.DEFAULT_RATE;
  }
  
  function safeRegex(src) {
    if (!src) return null;
    try { return new RegExp(String(src)); } catch (e) { return null; }
  }
  
  /***** OUTPUT *****/
  function ensureOutputHeader(sheet) {
    var headers = [
      'event_date','week_start','organizer_email','organizer_dept','organizer_title',
      'calendar_id','event_id','instance_start','instance_end','duration_hours',
      'attendees_count','internal_attendees_count','internal_only','recurring_event_id',
      'attendee_emails','attendee_titles','attendee_depts','meeting_cost'
    ];
    sheet.clear();
    sheet.getRange(1,1,1,headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
    return sheet;
  }
  
  function upsertRows(sheet, rows, keyCols) {
    if (rows.length === 0) return;
  
    var headers = sheet.getRange(1,1,1,sheet.getLastColumn()).getValues()[0];
    var keyIdxs = keyCols.map(function(k){ return headers.indexOf(k); });
    var lastRow = sheet.getLastRow();
  
    // Build existing index
    var existing = {};
    if (lastRow > 1) {
      var data = sheet.getRange(2,1,lastRow-1,headers.length).getValues();
      for (var i = 0; i < data.length; i++) {
        var r = data[i];
        var key = keyIdxs.map(function(idx){ return String(r[idx]); }).join('||');
        existing[key] = 2 + i; // row number
      }
    }
  
    // Decide appends vs updates
    var toAppend = [];
    var toUpdate = [];
    for (var j = 0; j < rows.length; j++) {
      var row = rows[j];
      var key = keyIdxs.map(function(idx){ return String(row[idx]); }).join('||');
      var rowNum = existing[key];
      if (rowNum) {
        toUpdate.push({ rowNum: rowNum, values: row });
      } else {
        toAppend.push(row);
      }
    }
  
    if (toAppend.length) {
      sheet.getRange(sheet.getLastRow()+1, 1, toAppend.length, headers.length).setValues(toAppend);
    }
    for (var u = 0; u < toUpdate.length; u++) {
      sheet.getRange(toUpdate[u].rowNum, 1, 1, headers.length).setValues([toUpdate[u].values]);
    }
  }
  
  /***** UTILITIES *****/
  function getDuration(ev) {
    // Handles timed events only (skip all-day)
    var start = ev.start ? (ev.start.dateTime || ev.start.date) : null;
    var end   = ev.end   ? (ev.end.dateTime   || ev.end.date)   : null;
    if (!start || !end) return { startIso: '', endIso: '', durationHours: 0 };
    if (String(start).length === 10 || String(end).length === 10) {
      // All-day -> skip
      return { startIso: start, endIso: end, durationHours: 0 };
    }
    var s = new Date(start);
    var e = new Date(end);
    var ms = Math.max(0, e - s);
    return { startIso: s.toISOString(), endIso: e.toISOString(), durationHours: ms / 3600000 }; // 3_600_000 -> 3600000
  }
  
  function isInternal(email) {
    return String(email).toLowerCase().slice(-('@' + CONFIG.DOMAIN).length) === ('@' + CONFIG.DOMAIN);
  }
  
  function addDays(d, n) {
    var x = new Date(d);
    x.setDate(x.getDate() + n);
    return x;
  }
  
  function isoDate(d) {
    return new Date(d).toISOString();
  }
  
  function getWeekStart(d) {
    var x = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var day = x.getUTCDay(); // 0=Sun
    var diff = (day + 6) % 7; // Monday as week start
    x.setUTCDate(x.getUTCDate() - diff);
    return x.toISOString().slice(0,10);
  }
  