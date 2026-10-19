const fs = require('fs');

console.log("Starting SAKSHI Frontend Login Verification Tests...\n");

const html = fs.readFileSync('C:/main project/frontend/index.html', 'utf8');
const js = fs.readFileSync('C:/main project/frontend/app.js', 'utf8');
const css = fs.readFileSync('C:/main project/frontend/style.css', 'utf8');

let passes = 0;
let failures = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  [PASS] ${message}`);
    passes++;
  } else {
    console.error(`  [FAIL] ${message}`);
    failures++;
  }
}

// 1. Text & Layout Content Verification
assert(js.includes('ScreenLogin'), "ScreenLogin component is defined in app.js");
assert(js.includes('SAKSHI'), "SAKSHI title present in login markup");
assert(js.includes('Explainable AI Investigation Companion'), "Subtitle 'Explainable AI Investigation Companion' present");
assert(js.includes('Digital Investigation Workstation'), "Subtitle 'Digital Investigation Workstation' present");
assert(js.includes('DEVELOPMENT / DEMO'), "Badge 'DEVELOPMENT / DEMO' present");
assert(js.includes('Officer Access'), "Section title 'Officer Access' present");
assert(js.includes('Phone Number'), "Field label 'Phone Number' present");
assert(js.includes('+91'), "Prefix '+91' present");
assert(js.includes('Enter officer phone number'), "Placeholder 'Enter officer phone number' present");
assert(js.includes('Continue to SAKSHI'), "Button 'Continue to SAKSHI' present");
assert(js.includes('Development mode — authentication is not enabled.'), "Informational note present");
assert(js.includes('SAKSHI Investigation Platform'), "Footer brand present");
assert(js.includes('Evidence') && js.includes('Integrity') && js.includes('Explainability') && js.includes('Human Review'), "Footer pillars present");

// 2. Navigation & Routing Verification
assert(js.includes('pattern: /^#\\/login$/'), "Route #/login registered in routes list");
assert(js.includes('pattern: /^#\\/cases$/'), "Existing route #/cases preserved");
assert(js.includes('isLogin'), "Routing check for empty hash/initial load implemented");
assert(js.includes('window.location.hash = "#/cases"'), "Button/form submission navigates to #/cases");
assert(js.includes('document.body.classList.add("login-active")'), "login-active class applied on login view");
assert(js.includes('document.body.classList.remove("login-active")'), "login-active class removed when navigating away");

// 3. No Authentication / Firebase Verification
assert(!js.includes('firebase.auth'), "No Firebase auth invocation");
assert(!js.includes('signInWithPhoneNumber'), "No Firebase phone auth invocation");
assert(!js.includes('RecaptchaVerifier'), "No reCAPTCHA / OTP verification invocation");

// 4. CSS Verification
assert(css.includes('body.login-active'), "body.login-active styles present in style.css");
assert(css.includes('body.login-active .app-sidebar'), "Sidebar hidden during login mode");
assert(css.includes('body.login-active .app-header'), "Header hidden during login mode");
assert(css.includes('.login-wrapper'), ".login-wrapper container styled in style.css");
assert(css.includes('.login-card'), ".login-card container styled in style.css");
assert(css.includes('.btn-login-continue'), ".btn-login-continue styled in style.css");
assert(css.includes('@media (max-width: 480px)'), "Mobile responsive styles included");

// 5. Backend Integrity Verification
const backendMain = fs.readFileSync('C:/main project/backend/app/main.py', 'utf8');
assert(backendMain.includes('app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")'), "Backend serves frontend static files intact");

console.log(`\nVerification Complete: ${passes} passed, ${failures} failed.`);

if (failures > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
