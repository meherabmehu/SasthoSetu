/* Bilingual strings and language switching.
 *
 * Bangla is the default. This is a Bangladeshi health service and most users
 * read Bangla more comfortably than English; English is the alternative, not
 * the baseline.
 */
const TRANSLATIONS = {
  bn: {
    'app.name': 'সাস্থ্যসেতু',
    'app.tagline': 'বাংলাদেশের ডিজিটাল স্বাস্থ্যসেবা',

    'nav.home': 'হোম',
    'nav.triage': 'উপসর্গ পরীক্ষা',
    'nav.doctors': 'ডাক্তার',
    'nav.appointments': 'অ্যাপয়েন্টমেন্ট',
    'nav.records': 'আমার রেকর্ড',
    'nav.hospitals': 'হাসপাতাল',
    'nav.pharmacy': 'ওষুধ খুঁজুন',
    'nav.dashboard': 'ড্যাশবোর্ড',
    'nav.login': 'লগইন',
    'nav.logout': 'লগআউট',
    'nav.register': 'নিবন্ধন',
    'nav.profile': 'প্রোফাইল',
    'nav.patients': 'রোগী',
    'nav.schedule': 'সময়সূচি',
    'nav.verify': 'যাচাই',

    'action.submit': 'জমা দিন',
    'action.cancel': 'বাতিল',
    'action.save': 'সংরক্ষণ',
    'action.search': 'খুঁজুন',
    'action.book': 'বুক করুন',
    'action.back': 'ফিরে যান',
    'action.next': 'পরবর্তী',
    'action.close': 'বন্ধ করুন',
    'action.retry': 'আবার চেষ্টা করুন',
    'action.view': 'দেখুন',
    'action.print': 'প্রিন্ট',

    'triage.title': 'উপসর্গ পরীক্ষা',
    'triage.subtitle': 'আপনার সমস্যা বাংলায় লিখুন বা বলুন',
    'triage.placeholder': 'যেমন: বুকে ব্যথা, শ্বাস নিতে কষ্ট, দুই দিন ধরে জ্বর',
    'triage.age': 'বয়স (বছর)',
    'triage.temperature': 'তাপমাত্রা (সে.)',
    'triage.analyze': 'পরীক্ষা করুন',
    'triage.analyzing': 'বিশ্লেষণ চলছে...',
    'triage.speak': 'কথা বলে বলুন',
    'triage.listening': 'শুনছি...',
    'triage.result': 'ফলাফল',
    'triage.matched': 'শনাক্ত হওয়া উপসর্গ',
    'triage.symptomsLabel': 'আপনার উপসর্গ',
    'triage.commonLabel': 'সাধারণ উপসর্গ (ট্যাপ করুন)',
    'triage.specialty': 'প্রস্তাবিত বিভাগ',
    'triage.confidence': 'নির্ভরযোগ্যতা',
    'triage.findDoctor': 'ডাক্তার খুঁজুন',
    'triage.findHospital': 'জরুরি হাসপাতাল খুঁজুন',
    'triage.history': 'আগের পরীক্ষা',
    'triage.emptyInput': 'অনুগ্রহ করে আপনার উপসর্গ লিখুন',

    'severity.1': 'ঘরে যত্ন',
    'severity.2': 'টেলিমেডিসিন',
    'severity.3': 'ডাক্তার দেখান',
    'severity.4': 'বিশেষজ্ঞ দেখান',
    'severity.5': 'জরুরি অবস্থা',

    'doctor.find': 'ডাক্তার খুঁজুন',
    'doctor.specialty': 'বিভাগ',
    'doctor.fee': 'ফি',
    'doctor.experience': 'অভিজ্ঞতা',
    'doctor.years': 'বছর',
    'doctor.nextSlot': 'পরবর্তী সময়',
    'doctor.verified': 'বিএমডিসি যাচাইকৃত',
    'doctor.noneFound': 'কোনো ডাক্তার পাওয়া যায়নি',

    'appointment.book': 'অ্যাপয়েন্টমেন্ট বুক করুন',
    'appointment.date': 'তারিখ',
    'appointment.time': 'সময়',
    'appointment.reason': 'সমস্যার বিবরণ',
    'appointment.status': 'অবস্থা',
    'appointment.mine': 'আমার অ্যাপয়েন্টমেন্ট',
    'appointment.none': 'কোনো অ্যাপয়েন্টমেন্ট নেই',
    'appointment.booked': 'অ্যাপয়েন্টমেন্ট নিশ্চিত হয়েছে',

    'hospital.title': 'হাসপাতাল ও শয্যা',
    'hospital.beds': 'খালি শয্যা',
    'hospital.icu': 'খালি আইসিইউ',
    'hospital.distance': 'দূরত্ব',
    'hospital.emergency': 'জরুরি বিভাগ আছে',
    'hospital.useLocation': 'আমার অবস্থান ব্যবহার করুন',
    'hospital.occupancy': 'শয্যা ব্যবহার',

    'pharmacy.title': 'ওষুধ খুঁজুন',
    'pharmacy.medicine': 'ওষুধের নাম',
    'pharmacy.inStock': 'মজুদ আছে',
    'pharmacy.price': 'দাম',
    'pharmacy.generic': 'জেনেরিক নাম',

    'prescription.title': 'প্রেসক্রিপশন',
    'prescription.code': 'যাচাই কোড',
    'prescription.verify': 'যাচাই করুন',
    'prescription.valid': 'বৈধ প্রেসক্রিপশন',
    'prescription.invalid': 'অবৈধ প্রেসক্রিপশন',
    'prescription.medicine': 'ওষুধ',
    'prescription.frequency': 'সেবনবিধি',
    'prescription.duration': 'মেয়াদ',
    'prescription.issued': 'প্রদানের তারিখ',
    'prescription.expires': 'মেয়াদ শেষ',
    'prescription.none': 'কোনো প্রেসক্রিপশন নেই',

    'auth.login': 'লগইন',
    'auth.register': 'নতুন অ্যাকাউন্ট',
    'auth.email': 'ইমেইল',
    'auth.password': 'পাসওয়ার্ড',
    'auth.name': 'পুরো নাম',
    'auth.phone': 'মোবাইল নম্বর',
    'auth.loggedOut': 'আপনি লগআউট করেছেন',
    'auth.needLogin': 'এই পাতা দেখতে লগইন করুন',
    'auth.invalid': 'ইমেইল বা পাসওয়ার্ড ভুল',

    'status.loading': 'লোড হচ্ছে...',
    'status.offline': 'ইন্টারনেট সংযোগ নেই — অফলাইন মোডে চলছে',
    'status.saved': 'সংরক্ষিত হয়েছে',
    'status.error': 'সমস্যা হয়েছে',
    'status.queued': 'সংযোগ ফিরলে পাঠানো হবে',
    'status.none': 'কিছু পাওয়া যায়নি',

    'triage.differential': 'সম্ভাব্য কারণ',
    'triage.likelihood': 'সম্ভাবনা',
    'triage.notDiagnosis': 'এটি সম্ভাব্য কারণের তালিকা, নিশ্চিত রোগ নির্ণয় নয়। নিশ্চিত হতে ডাক্তার দেখান।',
    'triage.basedOn': 'যেসব উপসর্গের ভিত্তিতে',
    'triage.urgentCare': 'জরুরি — দ্রুত চিকিৎসা প্রয়োজন',
    'rec.title': 'আপনার কাছাকাছি সেরা ডাক্তার',
    'rec.useLocation': 'আমার অবস্থান দিয়ে খুঁজুন',
    'rec.locating': 'অবস্থান খোঁজা হচ্ছে...',
    'rec.away': 'দূরে',
    'rec.reviews': 'রিভিউ',
    'rec.noReviews': 'এখনো রিভিউ নেই',
    'rec.verified': 'যাচাইকৃত রিভিউ',
    'rec.whyRanked': 'কেন এই ক্রম',
    'review.title': 'রিভিউ দিন',
    'review.pending': 'রিভিউ দেওয়ার অপেক্ষায়',
    'review.rating': 'সামগ্রিক রেটিং',
    'review.explanation': 'বুঝিয়ে বলা',
    'review.punctuality': 'সময়ানুবর্তিতা',
    'review.respect': 'ব্যবহার',
    'review.comment': 'আপনার মন্তব্য',
    'review.submit': 'রিভিউ জমা দিন',
    'review.proofNote': 'শুধু প্রকৃত সম্পন্ন কনসালটেশনের রিভিউ গ্রহণ করা হয়।',
    'review.thanks': 'ধন্যবাদ, আপনার রিভিউ যুক্ত হয়েছে।',
    'review.none': 'রিভিউ দেওয়ার মতো কোনো কনসালটেশন নেই।',
    'review.verifiedVisit': 'যাচাইকৃত ভিজিট',
    'disclaimer': 'এই ফলাফল সিদ্ধান্ত-সহায়ক তথ্য, রোগ নির্ণয় নয়। উপসর্গ তীব্র হলে দ্রুত চিকিৎসকের পরামর্শ নিন।',
    'emergency.call': 'জাতীয় জরুরি সেবা ৯৯৯ এ কল করুন',
  },

  en: {
    'app.name': 'SasthoSetu',
    'app.tagline': "Bangladesh's digital health service",

    'nav.home': 'Home',
    'nav.triage': 'Symptom check',
    'nav.doctors': 'Doctors',
    'nav.appointments': 'Appointments',
    'nav.records': 'My records',
    'nav.hospitals': 'Hospitals',
    'nav.pharmacy': 'Find medicine',
    'nav.dashboard': 'Dashboard',
    'nav.login': 'Log in',
    'nav.logout': 'Log out',
    'nav.register': 'Register',
    'nav.profile': 'Profile',
    'nav.patients': 'Patients',
    'nav.schedule': 'Schedule',
    'nav.verify': 'Verify',

    'action.submit': 'Submit',
    'action.cancel': 'Cancel',
    'action.save': 'Save',
    'action.search': 'Search',
    'action.book': 'Book',
    'action.back': 'Back',
    'action.next': 'Next',
    'action.close': 'Close',
    'action.retry': 'Try again',
    'action.view': 'View',
    'action.print': 'Print',

    'triage.title': 'Symptom check',
    'triage.subtitle': 'Describe your problem in Bangla or English',
    'triage.placeholder': 'For example: chest pain, difficulty breathing, fever for two days',
    'triage.age': 'Age (years)',
    'triage.temperature': 'Temperature (C)',
    'triage.analyze': 'Check symptoms',
    'triage.analyzing': 'Analysing...',
    'triage.speak': 'Speak instead',
    'triage.listening': 'Listening...',
    'triage.result': 'Result',
    'triage.matched': 'Recognised symptoms',
    'triage.symptomsLabel': 'Your symptoms',
    'triage.commonLabel': 'Common symptoms (tap to add)',
    'triage.specialty': 'Recommended specialty',
    'triage.confidence': 'Confidence',
    'triage.findDoctor': 'Find a doctor',
    'triage.findHospital': 'Find emergency hospital',
    'triage.history': 'Previous checks',
    'triage.emptyInput': 'Please describe your symptoms',

    'severity.1': 'Self care',
    'severity.2': 'Teleconsultation',
    'severity.3': 'See a doctor',
    'severity.4': 'See a specialist',
    'severity.5': 'Emergency',

    'doctor.find': 'Find a doctor',
    'doctor.specialty': 'Specialty',
    'doctor.fee': 'Fee',
    'doctor.experience': 'Experience',
    'doctor.years': 'years',
    'doctor.nextSlot': 'Next available',
    'doctor.verified': 'BMDC verified',
    'doctor.noneFound': 'No doctors found',

    'appointment.book': 'Book an appointment',
    'appointment.date': 'Date',
    'appointment.time': 'Time',
    'appointment.reason': 'Reason for visit',
    'appointment.status': 'Status',
    'appointment.mine': 'My appointments',
    'appointment.none': 'No appointments yet',
    'appointment.booked': 'Appointment confirmed',

    'hospital.title': 'Hospitals and beds',
    'hospital.beds': 'Available beds',
    'hospital.icu': 'Available ICU',
    'hospital.distance': 'Distance',
    'hospital.emergency': 'Has emergency department',
    'hospital.useLocation': 'Use my location',
    'hospital.occupancy': 'Bed occupancy',

    'pharmacy.title': 'Find medicine',
    'pharmacy.medicine': 'Medicine name',
    'pharmacy.inStock': 'In stock',
    'pharmacy.price': 'Price',
    'pharmacy.generic': 'Generic name',

    'prescription.title': 'Prescription',
    'prescription.code': 'Verification code',
    'prescription.verify': 'Verify',
    'prescription.valid': 'Valid prescription',
    'prescription.invalid': 'Invalid prescription',
    'prescription.medicine': 'Medicine',
    'prescription.frequency': 'Dosage',
    'prescription.duration': 'Duration',
    'prescription.issued': 'Issued',
    'prescription.expires': 'Expires',
    'prescription.none': 'No prescriptions yet',

    'auth.login': 'Log in',
    'auth.register': 'Create account',
    'auth.email': 'Email',
    'auth.password': 'Password',
    'auth.name': 'Full name',
    'auth.phone': 'Mobile number',
    'auth.loggedOut': 'You have been logged out',
    'auth.needLogin': 'Please log in to view this page',
    'auth.invalid': 'Incorrect email or password',

    'status.loading': 'Loading...',
    'status.offline': 'No connection - working offline',
    'status.saved': 'Saved',
    'status.error': 'Something went wrong',
    'status.queued': 'Will be sent when you are back online',
    'status.none': 'Nothing found',

    'triage.differential': 'Possible causes',
    'triage.likelihood': 'Likelihood',
    'triage.notDiagnosis': 'These are possibilities, not a confirmed diagnosis. See a doctor to be sure.',
    'triage.basedOn': 'Based on',
    'triage.urgentCare': 'Urgent - needs prompt medical care',
    'rec.title': 'Best doctors near you',
    'rec.useLocation': 'Search near my location',
    'rec.locating': 'Finding your location...',
    'rec.away': 'away',
    'rec.reviews': 'reviews',
    'rec.noReviews': 'No reviews yet',
    'rec.verified': 'verified reviews',
    'rec.whyRanked': 'Why this order',
    'review.title': 'Leave a review',
    'review.pending': 'Awaiting your review',
    'review.rating': 'Overall rating',
    'review.explanation': 'Explained clearly',
    'review.punctuality': 'Punctuality',
    'review.respect': 'Respectfulness',
    'review.comment': 'Your comment',
    'review.submit': 'Submit review',
    'review.proofNote': 'Only reviews from consultations that actually took place are accepted.',
    'review.thanks': 'Thank you, your review has been recorded.',
    'review.none': 'You have no consultations available to review.',
    'review.verifiedVisit': 'Verified visit',
    'disclaimer': 'This is decision support, not a diagnosis. If symptoms are severe or worsening, seek care from a qualified professional.',
    'emergency.call': 'Call the national emergency service on 999',
  },
};

const STORAGE_KEY = 'sasthosetu.lang';

export const i18n = {
  lang: localStorage.getItem(STORAGE_KEY) || 'bn',

  t(key) {
    const table = TRANSLATIONS[this.lang] || TRANSLATIONS.bn;
    return table[key] ?? TRANSLATIONS.bn[key] ?? key;
  },

  setLang(lang) {
    if (!TRANSLATIONS[lang]) return;
    this.lang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.lang = lang;
    this.apply();
    window.dispatchEvent(new CustomEvent('languagechange', { detail: { lang } }));
  },

  toggle() {
    this.setLang(this.lang === 'bn' ? 'en' : 'bn');
  },

  /** Replace the text of every element carrying a data-i18n key. */
  apply(root = document) {
    root.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = this.t(el.dataset.i18n);
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      el.placeholder = this.t(el.dataset.i18nPlaceholder);
    });
    root.querySelectorAll('[data-i18n-label]').forEach((el) => {
      el.setAttribute('aria-label', this.t(el.dataset.i18nLabel));
    });
    document.documentElement.lang = this.lang;
  },

  /** Pick the Bangla or English variant of a bilingual API response. */
  pick(enValue, bnValue) {
    return this.lang === 'bn' && bnValue ? bnValue : enValue;
  },
};

document.documentElement.lang = i18n.lang;
