# Signing in with your work account

Sign in to a managed workstation and the staff portal with your work account. The same account is used for email, file shares and the VPN, so one successful sign-in confirms all three.

| Field | Value |
| --- | --- |
| Applies to | Windows 10/11 workstations and the staff portal |
| Audience | beginner staff |
| Time needed | 5 minutes |
| Owner | IT Service Desk |

## Before you begin

- Your work email address in the form firstname.lastname@example.com.
- Your current password. If it has expired, reset it first.
- An enrolled multi-factor device (phone app or hardware key).
- A connection to the corporate network or the VPN, not guest Wi-Fi.

## Step-by-step

1. Check your network connection
   Join Corp-Staff Wi-Fi or start the VPN before signing in. The sign-in prompt cannot reach the identity service from a guest or home network.

2. Open the sign-in screen
   Press Ctrl+Alt+Delete on a workstation, or open https://portal.example.com in a browser.

3. Enter your work email address
   Use the full work address. Personal accounts and old usernames are rejected even when the password is correct.

4. Enter your password
   Type the password you set at onboarding. Check Caps Lock and the keyboard layout before trying again.

5. Approve the multi-factor prompt
   Approve the request in the authenticator app, or type the current six-digit code. Prompts expire after 60 seconds.

6. Confirm the session
   The desktop or portal home page opens with your name in the top-right corner. If the page returns to the login form, see Troubleshooting.

### Helpful hints

- The network icon in the taskbar shows a filled signal bar, and the VPN client shows Connected.
- The eye icon reveals what you typed; use it instead of retyping blindly.

## Verify it worked

- [ ] Your name and photo appear in the portal header.
- [ ] The workstation is listed under My devices.
- [ ] The intranet opens without asking you to sign in again.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| “Invalid username or password” | Re-type the address in lower case, check Caps Lock, then retry once. Two more failures lock the account, so use the password reset guide instead of guessing. |
| “Account locked” | Wait 15 minutes for the automatic unlock, or ask the service desk to release it. Retrying extends the lockout. |
| No multi-factor prompt arrives | Check the phone has signal and the app is still enrolled. Choose “Use a verification code” and type the six digits shown in the app. |
| Sign-in loops back to the form | Clear cookies for the portal or open it in a private window; a stale session cookie causes the loop. If it persists, sign out at portal.example.com/signout. |

## Related guides

- Reset your password
- Set up multi-factor authentication
- Connect to the VPN

## If you need more help

Contact the IT Service Desk on ext. 4357 or it-servicedesk@example.com, quoting the asset name and the exact error text. Include what you tried and the exact wording of any error message.

## Document control

| Field | Value |
| --- | --- |
| Document | Signing in with your work account |
| Owner | IT Service Desk |
| Review cycle | Every 6 months, or after a platform change |
| Scope | Windows 10/11 workstations and the staff portal |
| Feedback | Reply to the guide's announcement or raise a ticket |
