"""Built-in IT playbooks and the guide layout they produce.

A playbook is the part a person should not have to retype: purpose,
prerequisites, ordered steps, a verification list and the four failures that
actually happen.  The brief chooses the playbook; tone, audience and detail
reshape it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .blocks import Block, BulletList, ListItem
from .build import bullets, checklist, h, kv_table, p, steps, table
from .markdown import parse_inline
from .prefs import Prefs, hint, shape


@dataclass(frozen=True)
class Step:
    title: str
    detail: str
    tip: str = ""


@dataclass(frozen=True)
class Playbook:
    key: str
    title: str
    purpose: str
    aliases: tuple[str, ...]
    applies_to: str
    time: str
    prerequisites: tuple[str, ...]
    steps: tuple[Step, ...]
    verify: tuple[str, ...]
    troubleshooting: tuple[tuple[str, str], ...]
    related: tuple[str, ...] = ()
    escalation: str = (
        "the IT Service Desk on ext. 4357 or it-servicedesk@example.com, quoting the "
        "asset name and the exact error text"
    )


PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook(
        key="login",
        title="Signing in with your work account",
        purpose=(
            "Sign in to a managed workstation and the staff portal with your work account. "
            "The same account is used for email, file shares and the VPN, so one successful "
            "sign-in confirms all three."
        ),
        aliases=("login", "log in", "sign in", "signin", "logon", "workstation login"),
        applies_to="Windows 10/11 workstations and the staff portal",
        time="5 minutes",
        prerequisites=(
            "Your work email address in the form firstname.lastname@example.com.",
            "Your current password. If it has expired, reset it first.",
            "An enrolled multi-factor device (phone app or hardware key).",
            "A connection to the corporate network or the VPN, not guest Wi-Fi.",
        ),
        steps=(
            Step(
                "Check your network connection",
                "Join Corp-Staff Wi-Fi or start the VPN before signing in. The sign-in prompt "
                "cannot reach the identity service from a guest or home network.",
                "The network icon in the taskbar shows a filled signal bar, and the VPN client "
                "shows Connected.",
            ),
            Step(
                "Open the sign-in screen",
                "Press Ctrl+Alt+Delete on a workstation, or open https://portal.example.com in "
                "a browser.",
            ),
            Step(
                "Enter your work email address",
                "Use the full work address. Personal accounts and old usernames are rejected "
                "even when the password is correct.",
            ),
            Step(
                "Enter your password",
                "Type the password you set at onboarding. Check Caps Lock and the keyboard "
                "layout before trying again.",
                "The eye icon reveals what you typed; use it instead of retyping blindly.",
            ),
            Step(
                "Approve the multi-factor prompt",
                "Approve the request in the authenticator app, or type the current six-digit "
                "code. Prompts expire after 60 seconds.",
            ),
            Step(
                "Confirm the session",
                "The desktop or portal home page opens with your name in the top-right corner. "
                "If the page returns to the login form, see Troubleshooting.",
            ),
        ),
        verify=(
            "Your name and photo appear in the portal header.",
            "The workstation is listed under My devices.",
            "The intranet opens without asking you to sign in again.",
        ),
        troubleshooting=(
            (
                "“Invalid username or password”",
                "Re-type the address in lower case, check Caps Lock, then retry once. Two more "
                "failures lock the account, so use the password reset guide instead of guessing.",
            ),
            (
                "“Account locked”",
                "Wait 15 minutes for the automatic unlock, or ask the service desk to release "
                "it. Retrying extends the lockout.",
            ),
            (
                "No multi-factor prompt arrives",
                "Check the phone has signal and the app is still enrolled. Choose “Use a "
                "verification code” and type the six digits shown in the app.",
            ),
            (
                "Sign-in loops back to the form",
                "Clear cookies for the portal or open it in a private window; a stale session "
                "cookie causes the loop. If it persists, sign out at portal.example.com/signout.",
            ),
        ),
        related=("Reset your password", "Set up multi-factor authentication", "Connect to the VPN"),
    ),
    Playbook(
        key="password-reset",
        title="Resetting your work password",
        purpose=(
            "Reset a forgotten or expired work password without calling the service desk. "
            "The new password is used immediately and must be changed again only when policy "
            "expires it."
        ),
        aliases=("password", "reset password", "forgot password", "expired password", "change password"),
        applies_to="All staff accounts",
        time="10 minutes",
        prerequisites=(
            "Access to the mailbox or phone registered for multi-factor authentication.",
            "A device connected to the corporate network or VPN.",
        ),
        steps=(
            Step(
                "Open the password reset page",
                "Go to https://password.example.com and choose “Reset my password”.",
            ),
            Step(
                "Confirm your identity",
                "Enter your work email address, then approve the multi-factor prompt or type "
                "the code sent to your registered phone.",
                "If the registered phone is lost, stop here and call the service desk; identity "
                "verification cannot be bypassed online.",
            ),
            Step(
                "Choose a new password",
                "Use at least 14 characters with three of the four character types. It cannot "
                "match any of your last five passwords or contain your name.",
            ),
            Step(
                "Update saved credentials",
                "Sign out and back in on the phone mail app, mapped drives and the VPN client. "
                "Each keeps its own cached copy of the old password.",
            ),
            Step(
                "Sign in once from the workstation",
                "A successful sign-in at the workstation clears the “password expired” state for "
                "all connected services.",
            ),
        ),
        verify=(
            "The portal accepts the new password.",
            "The old password is rejected.",
            "Mail arrives on the phone without a password prompt.",
        ),
        troubleshooting=(
            (
                "The reset link expired",
                "Links are valid for 15 minutes. Request a new one and complete the form in a "
                "single session.",
            ),
            (
                "The new password is rejected",
                "Check the length first, then whether the password contains your username or a "
                "previous password. Reusing a password is the usual cause.",
            ),
            (
                "The registered phone has changed",
                "Only the service desk can re-register a multi-factor device; bring photo ID.",
            ),
            (
                "The account stays locked after the reset",
                "The lock clears after 15 minutes. Signing in repeatedly restarts the timer.",
            ),
        ),
        related=("Signing in with your work account", "Set up multi-factor authentication"),
    ),
    Playbook(
        key="mfa",
        title="Setting up multi-factor authentication",
        purpose=(
            "Enrol a phone or hardware key for multi-factor authentication, and replace a "
            "device that has been lost or upgraded."
        ),
        aliases=("mfa", "multi-factor", "2fa", "authenticator", "one-time code", "security key"),
        applies_to="All staff accounts",
        time="10 minutes",
        prerequisites=(
            "A smartphone with the company-approved authenticator app installed.",
            "Your work account signed in on a computer.",
            "A password manager or safe place for the backup codes.",
        ),
        steps=(
            Step(
                "Open the security settings",
                "Go to https://account.example.com/security and choose “Add sign-in method”.",
            ),
            Step(
                "Choose Authenticator app",
                "Select “Authenticator app”, then “Add” to show the enrolment QR code.",
            ),
            Step(
                "Scan the code",
                "In the app, choose “Add account”, scan the QR code, and accept the test prompt "
                "the portal sends.",
                "If the camera will not focus, use “Enter code manually” and type the key shown "
                "under the QR code.",
            ),
            Step(
                "Store the backup codes",
                "Download the ten single-use codes and keep them in the password manager, not in "
                "the mailbox they protect.",
            ),
            Step(
                "Remove the old device",
                "Delete the previous phone or key from the sign-in methods list only after the "
                "new device has approved a prompt.",
            ),
        ),
        verify=(
            "The new device appears in the sign-in methods list.",
            "A test sign-in approves from the new device.",
            "The old device no longer receives prompts.",
        ),
        troubleshooting=(
            (
                "The QR code will not scan",
                "Increase screen brightness and hold the phone 15 cm away, or use the manual "
                "code under the QR image.",
            ),
            (
                "Every code is rejected",
                "The phone clock has drifted. Set date and time to automatic, then try again.",
            ),
            (
                "The phone is lost",
                "Call the service desk to revoke the device and issue temporary access. Use a "
                "backup code if one is stored safely.",
            ),
            (
                "A prompt arrives that you did not start",
                "Deny it and report it: someone has your password. Change the password "
                "immediately afterwards.",
            ),
        ),
        related=("Signing in with your work account", "Resetting your work password"),
    ),
    Playbook(
        key="vpn",
        title="Connecting to the VPN",
        purpose=(
            "Reach the corporate network from home or a customer site so file shares, intranet "
            "and internal applications behave as they do in the office."
        ),
        aliases=("vpn", "remote access", "tunnel", "work from home", "home network"),
        applies_to="Managed laptops with the VPN client installed",
        time="5 minutes",
        prerequisites=(
            "The company VPN client installed from the Company Portal.",
            "A working internet connection and an enrolled multi-factor device.",
            "Your work account, with permission to use the full-tunnel profile.",
        ),
        steps=(
            Step(
                "Open the VPN client",
                "Start the client from the taskbar tray or the Start menu.",
            ),
            Step(
                "Select the staff profile",
                "Choose “Staff – Full tunnel”. The split-tunnel profile is for approved "
                "engineering use only.",
            ),
            Step(
                "Sign in and approve the prompt",
                "Use your work email address and password, then approve the multi-factor "
                "request.",
            ),
            Step(
                "Wait for the tunnel to establish",
                "The client shows Connected with a session timer. This usually takes under "
                "20 seconds.",
            ),
            Step(
                "Test an internal address",
                "Open the intranet or a mapped drive. The first connection after sign-in can "
                "take a few seconds while DNS resolves.",
                "A captive-portal Wi-Fi (hotel, café) blocks the tunnel until you sign in to "
                "that network's own page.",
            ),
        ),
        verify=(
            "The client reports Connected and a session timer.",
            "The intranet loads without a certificate warning.",
            "\\\\fileserver\\staff opens in File Explorer.",
        ),
        troubleshooting=(
            (
                "“Authentication failed”",
                "Sign in to the portal once in a browser to confirm the password, then retry. "
                "An expired password fails in the client without saying so.",
            ),
            (
                "Connects, then drops repeatedly",
                "A captive portal or unstable Wi-Fi is the usual cause. Sign in to the network, "
                "or switch to a mobile hotspot to confirm.",
            ),
            (
                "Intranet works but file shares do not",
                "Disconnect and reconnect the tunnel so DNS is re-registered; then run "
                "`ipconfig /flushdns` in a command prompt.",
            ),
            (
                "The client hangs on “Connecting”",
                "Restart the VPN service: right-click the tray icon, choose Quit, then start the "
                "client again. A pending Windows update can also block it.",
            ),
        ),
        related=("Signing in with your work account", "Connecting to staff Wi-Fi"),
    ),
    Playbook(
        key="wifi",
        title="Connecting to staff Wi-Fi",
        purpose=(
            "Join a laptop or phone to the staff wireless network with the certificate-based "
            "profile, and understand why the guest network behaves differently."
        ),
        aliases=("wifi", "wi-fi", "wireless", "network connection", "ssid"),
        applies_to="Laptops, phones and tablets",
        time="5 minutes",
        prerequisites=(
            "Your work account and password.",
            "The device within range of an office access point.",
            "The company root certificate installed (managed devices have it already).",
        ),
        steps=(
            Step(
                "Select the staff network",
                "Choose “Corp-Staff” from the Wi-Fi list. “Corp-Guest” is for visitors and cannot "
                "reach internal systems.",
            ),
            Step(
                "Choose the enterprise settings",
                "Method PEAP, phase 2 MSCHAPv2, and “Use my Windows user name” left unticked.",
            ),
            Step(
                "Enter your credentials",
                "Username is your work email address; the password is your current work "
                "password.",
            ),
            Step(
                "Accept the certificate",
                "Confirm the certificate is issued to corp-wifi.example.com before accepting. "
                "A different name means you have joined a look-alike network.",
                "Read the certificate name, not just the prompt. Accepting the wrong one hands "
                "your password to whoever runs that access point.",
            ),
            Step(
                "Confirm the connection",
                "The network shows Connected and the intranet loads.",
            ),
        ),
        verify=(
            "The Wi-Fi list shows Corp-Staff as connected.",
            "The intranet loads in the browser.",
            "The device gets an address in the 10.20.x.x range.",
        ),
        troubleshooting=(
            (
                "Corp-Staff is not listed",
                "Move closer to an access point and refresh the list; a disabled Wi-Fi adapter "
                "or airplane mode hides all networks.",
            ),
            (
                "The certificate warning repeats",
                "Forget the network, then rejoin and accept only the certificate named "
                "corp-wifi.example.com.",
            ),
            (
                "Connected but no internet",
                "The device may have an old static IP. Set the adapter back to DHCP and "
                "reconnect.",
            ),
            (
                "Works on the phone but not the laptop",
                "Update the wireless driver from the Company Portal; stale drivers fail the "
                "PEAP handshake silently.",
            ),
        ),
        related=("Connecting to the VPN", "Signing in with your work account"),
    ),
    Playbook(
        key="printer",
        title="Adding an office printer and clearing the print queue",
        purpose=(
            "Add a floor printer by queue name, print a test page, and clear the jobs that "
            "block everyone else on that queue."
        ),
        aliases=("printer", "printing", "print queue", "scan to email", "scanner", "toner"),
        applies_to="Printers on the office print server",
        time="10 minutes",
        prerequisites=(
            "A managed device connected to the corporate network or VPN.",
            "The queue name from the label on the printer (for example PRN-3F-EAST).",
        ),
        steps=(
            Step(
                "Add the printer by queue name",
                "Open Settings → Bluetooth & devices → Printers & scanners → Add device, then "
                "choose “Add manually” and enter \\\\printserver\\PRN-3F-EAST.",
            ),
            Step(
                "Set it as default",
                "Open the printer's entry and choose “Set as default” so documents stop going to "
                "the last printer used.",
            ),
            Step(
                "Print a test page",
                "Choose “Print a test page”. Confirm the job appears in the queue with a status "
                "of Printing or Sent.",
                "A test page that never leaves the queue is a queue problem, not a document "
                "problem.",
            ),
            Step(
                "Clear a stuck queue",
                "Open the queue, cancel the oldest job first, then restart the Print Spooler "
                "service if the status stays “Deleting”.",
            ),
            Step(
                "Check supplies before reporting",
                "The printer panel shows toner levels and any paper jam code. Note the code "
                "when you call the service desk.",
            ),
        ),
        verify=(
            "The test page prints and the queue empties.",
            "The printer shows Ready, not Offline or Paused.",
            "Other colleagues can print after the blocked job is cleared.",
        ),
        troubleshooting=(
            (
                "The printer is not listed",
                "Type the queue name directly; discovery is blocked on some subnets even when "
                "printing works.",
            ),
            (
                "Jobs stay at “Deleting”",
                "Restart the Print Spooler service from Services, then reopen the queue.",
            ),
            (
                "Documents print on the wrong printer",
                "Set the correct printer as default and remove the stale one from the list.",
            ),
            (
                "Scan-to-email does not arrive",
                "Check the spam folder, then confirm the printer has the correct address book "
                "entry; quarantined scans are released by the mail team.",
            ),
        ),
        related=("Connecting to the VPN", "Signing in with your work account"),
    ),
    Playbook(
        key="email",
        title="Setting up work email on desktop and phone",
        purpose=(
            "Add the work mailbox to Outlook on a laptop and to the mail app on a phone, then "
            "confirm mail, calendar and shared mailboxes synchronise."
        ),
        aliases=("email", "outlook", "mailbox", "calendar", "mail setup"),
        applies_to="Outlook for Windows and the Outlook mobile app",
        time="15 minutes",
        prerequisites=(
            "Your work account details and an enrolled multi-factor device.",
            "An active Microsoft 365 licence assigned to the account.",
        ),
        steps=(
            Step(
                "Open Outlook and choose Add account",
                "On a new profile, choose File → Add Account; on a phone, use Settings → Add "
                "Mail Account → Outlook.",
            ),
            Step(
                "Enter the work address",
                "Use the full work email address. Outlook should find the settings "
                "automatically.",
            ),
            Step(
                "Approve the multi-factor prompt",
                "Complete the prompt once on each device. The phone app asks again separately.",
            ),
            Step(
                "Let the first sync finish",
                "A large mailbox can take several minutes. Leave Outlook open until the status "
                "bar reads “All folders are up to date”.",
            ),
            Step(
                "Open a shared mailbox",
                "Choose File → Account Settings → Change → More Settings → Advanced → Add, and "
                "enter the shared mailbox address.",
                "Shared mailboxes need permission from the mailbox owner; the service desk "
                "cannot grant it without their approval.",
            ),
            Step(
                "Send a test message",
                "Send a short message to yourself and confirm it arrives on both devices.",
            ),
        ),
        verify=(
            "Inbox and calendar show the current content.",
            "A test message arrives on the phone within a minute.",
            "The shared mailbox appears in the folder list.",
        ),
        troubleshooting=(
            (
                "Outlook cannot find the account",
                "Confirm the licence is assigned and the address is spelled exactly; then add "
                "the account manually as Microsoft 365.",
            ),
            (
                "“Mailbox is full”",
                "Empty Deleted Items and Sent Items, or archive older mail. The quota is shared "
                "with the online archive.",
            ),
            (
                "A shared mailbox is missing",
                "Check that permission was granted, then restart Outlook so it reads the new "
                "permissions.",
            ),
            (
                "The phone stops syncing",
                "Re-authenticate the account in the phone's settings; cached tokens expire "
                "after a password change.",
            ),
        ),
        related=("Opening and using a shared mailbox", "Signing in with your work account"),
    ),
    Playbook(
        key="software-install",
        title="Installing approved software",
        purpose=(
            "Install approved applications from the Company Portal without local administrator "
            "rights, and know what to do when an application is not offered."
        ),
        aliases=("install software", "software", "application", "company portal", "app install"),
        applies_to="Managed Windows devices",
        time="10 minutes",
        prerequisites=(
            "A managed device with the Company Portal installed.",
            "Enough free disk space (the portal shows the requirement).",
            "A connection to the corporate network or VPN.",
        ),
        steps=(
            Step(
                "Open the Company Portal",
                "Search the Start menu for “Company Portal” and sign in with your work account.",
            ),
            Step(
                "Find the application",
                "Use the search box. Applications are grouped by category and by the licence "
                "your role holds.",
            ),
            Step(
                "Choose Install",
                "Select the application and press Install. Leave the portal open while it "
                "downloads.",
                "Elevation is handled by the portal; you will not be asked for an administrator "
                "password.",
            ),
            Step(
                "Wait for the install status",
                "Status moves from Downloading to Installing to Installed. A large package can "
                "take several minutes.",
            ),
            Step(
                "Launch and sign in",
                "Start the application from the Start menu and sign in with your work account "
                "if it asks.",
            ),
        ),
        verify=(
            "The application appears in the Start menu.",
            "The licence or subscription page shows an active seat.",
            "The portal status reads Installed.",
        ),
        troubleshooting=(
            (
                "The application is not listed",
                "It may need a licence or approval. Request it in the portal; approval normally "
                "arrives the same working day.",
            ),
            (
                "The install fails with an error code",
                "Note the code, free disk space and retry once. Repeated failures are usually a "
                "leftover previous version.",
            ),
            (
                "It asks for administrator rights",
                "Close the installer and use the Company Portal version; direct installers are "
                "blocked by policy.",
            ),
            (
                "“Licence not available”",
                "Ask the service desk to check the licence count for your role before "
                "reinstalling.",
            ),
        ),
        related=("Signing in with your work account", "Connecting to the VPN"),
    ),
    Playbook(
        key="backup",
        title="Backing up files and restoring a previous version",
        purpose=(
            "Confirm work files are protected by OneDrive, and restore an earlier version of a "
            "file that was overwritten or deleted."
        ),
        aliases=("backup", "back up", "restore file", "previous version", "onedrive", "lost file"),
        applies_to="Staff documents stored in OneDrive or team sites",
        time="10 minutes",
        prerequisites=(
            "OneDrive signed in with your work account.",
            "The file is stored in a synced folder (Desktop, Documents, Pictures or a team "
            "site).",
        ),
        steps=(
            Step(
                "Check OneDrive is syncing",
                "The cloud icon in the taskbar shows “Up to date”. A paused or signed-out client "
                "protects nothing.",
            ),
            Step(
                "Confirm the folders in scope",
                "Right-click the OneDrive icon → Settings → Account, and check Desktop, Documents "
                "and Pictures are listed under “Choose folders”.",
            ),
            Step(
                "Restore a previous version",
                "In File Explorer, right-click the file → Version history, and open the version "
                "from before the change.",
                "Version history needs the file to be synced; a file on the local C: drive has "
                "no history to show.",
            ),
            Step(
                "Restore a deleted file",
                "Open the OneDrive recycle bin in the browser and restore the file within 30 "
                "days.",
            ),
            Step(
                "Verify the restored copy",
                "Open the restored file and check the last paragraph and the modified date "
                "before continuing work.",
            ),
        ),
        verify=(
            "The OneDrive icon reports Up to date.",
            "Version history lists versions from the last 30 days.",
            "The restored file opens with the expected content.",
        ),
        troubleshooting=(
            (
                "OneDrive is paused",
                "Choose Resume syncing from the tray menu, then check the account for a "
                "re-authentication prompt.",
            ),
            (
                "Version history is empty",
                "The file is outside a synced folder. Move it into OneDrive and versions start "
                "from that point.",
            ),
            (
                "Sync conflicts create a duplicate",
                "Keep the copy with the newest content and delete the duplicate; both are "
                "preserved until you choose.",
            ),
            (
                "Storage is full",
                "Empty the recycle bin and remove old large files, or request more space from "
                "the service desk.",
            ),
        ),
        related=("Signing in with your work account", "Installing approved software"),
    ),
    Playbook(
        key="onboarding",
        title="New starter IT setup",
        purpose=(
            "Take a new colleague from an empty desk to a working account on their first "
            "morning: sign-in, multi-factor, network, mail, drives and the standard "
            "applications."
        ),
        aliases=("onboarding", "new starter", "new hire", "first day", "induction", "setup laptop"),
        applies_to="New staff and contractors on day one",
        time="45 minutes",
        prerequisites=(
            "The starter's account has been created and the licence assigned.",
            "A prepared device with the standard image and a named asset tag.",
            "A buddy or line manager available for the first sign-in.",
        ),
        steps=(
            Step(
                "Sign in for the first time",
                "Use the temporary password issued to the manager and set a new password when "
                "prompted.",
            ),
            Step(
                "Enrol multi-factor authentication",
                "Follow the enrolment prompt and install the authenticator app on the starter's "
                "phone.",
            ),
            Step(
                "Join the corporate network",
                "Connect to Corp-Staff Wi-Fi, then start the VPN once to confirm remote access "
                "works.",
            ),
            Step(
                "Set up mail and calendar",
                "Open Outlook, add the work account and let the first sync complete.",
            ),
            Step(
                "Map the team drives",
                "In File Explorer choose “Map network drive” and add \\\\fileserver\\staff and the "
                "team folder named in the handover notes.",
                "Write the drive letters on the handover sheet; support calls on day two are "
                "usually a missing drive letter.",
            ),
            Step(
                "Install the standard applications",
                "From the Company Portal install Teams, the PDF reader and any role-specific "
                "application on the handover notes.",
            ),
            Step(
                "Confirm the setup with the starter",
                "Ask them to send a test email, open the team site and join a short Teams call "
                "before the handover ends.",
            ),
        ),
        verify=(
            "The starter signs in without help.",
            "Mail arrives on the phone and the laptop.",
            "Team drives and the standard applications open.",
        ),
        troubleshooting=(
            (
                "The account does not exist yet",
                "Account creation needs the signed starter form. The service desk can confirm "
                "whether it was received.",
            ),
            (
                "No licence for mail",
                "The manager must approve the licence; it is not part of the default account.",
            ),
            (
                "Multi-factor enrolment loops",
                "Complete enrolment on the laptop browser, not inside the phone setup wizard.",
            ),
            (
                "A team drive is missing",
                "Check group membership first; drive mappings follow the group, not the person.",
            ),
        ),
        related=("Signing in with your work account", "Setting up multi-factor authentication"),
    ),
    Playbook(
        key="remote-desktop",
        title="Connecting to your office PC from home",
        purpose=(
            "Use Remote Desktop over the VPN to reach your office workstation, including mapped "
            "drives and printers."
        ),
        aliases=("remote desktop", "rdp", "office pc", "remote pc", "work from home pc"),
        applies_to="Staff with a permanently assigned office workstation",
        time="10 minutes",
        prerequisites=(
            "The VPN client, connected and showing a session timer.",
            "The workstation hostname from the asset label (for example WKS-0421).",
            "Permission for remote access, granted by the line manager.",
        ),
        steps=(
            Step(
                "Start the VPN",
                "Connect to “Staff – Full tunnel” and wait for the session timer.",
            ),
            Step(
                "Open Remote Desktop",
                "Search the Start menu for “Remote Desktop Connection”.",
            ),
            Step(
                "Enter the hostname",
                "Type the asset hostname, not the IP address; addresses change between office "
                "subnets.",
            ),
            Step(
                "Sign in with your work account",
                "Use the format EXAMPLE\\firstname.lastname and approve the multi-factor prompt "
                "on the phone.",
                "The prompt goes to the phone, not to the office PC, so keep it nearby.",
            ),
            Step(
                "Reconnect drives and printers",
                "In the Remote Desktop options, enable the local drives and printers before "
                "connecting if they are missing.",
            ),
            Step(
                "Sign out, do not disconnect",
                "Use Start → Sign out so the session releases the workstation for the next "
                "person.",
            ),
        ),
        verify=(
            "The office desktop appears with your icons.",
            "Mapped drives open in the remote session.",
            "The office printer is available from the print dialog.",
        ),
        troubleshooting=(
            (
                "“Computer not found”",
                "The VPN is not connected or the hostname is wrong. Confirm both, then retry.",
            ),
            (
                "Credentials are rejected",
                "Use the EXAMPLE\\username form; a Microsoft account alias fails even with the "
                "right password.",
            ),
            (
                "The session disconnects after a few minutes",
                "Idle timeouts are policy. Use “Reconnect” rather than starting a new session.",
            ),
            (
                "Local printers are missing",
                "Set the printer redirection option before connecting, then reconnect the "
                "session.",
            ),
        ),
        related=("Connecting to the VPN", "Signing in with your work account"),
    ),
    Playbook(
        key="phishing",
        title="Recognising and reporting a suspicious email",
        purpose=(
            "Decide quickly whether a message is genuine, report it without clicking, and limit "
            "the damage if it has already been opened."
        ),
        aliases=("phishing", "suspicious email", "scam", "spam", "report email", "fraud"),
        applies_to="All staff with a work mailbox",
        time="3 minutes",
        prerequisites=(
            "The Report Message button in Outlook (installed by default).",
            "The service desk number stored somewhere other than email.",
        ),
        steps=(
            Step(
                "Pause before acting",
                "Urgency, payment requests and “verify your account” links are the three most "
                "common signs. No genuine process needs your password by email.",
            ),
            Step(
                "Check the sender and the link target",
                "Hover the address and the link without clicking. The domain after the @ and "
                "before the first single slash is what matters.",
                "A display name can say anything; only the domain is real.",
            ),
            Step(
                "Report without opening attachments",
                "With the message selected, choose Report Message → Phishing. Do not forward it "
                "to colleagues to ask.",
            ),
            Step(
                "Delete only when instructed",
                "The security team may need the message in place while it investigates; follow "
                "their reply.",
            ),
            Step(
                "If you already clicked or entered credentials",
                "Disconnect from the network, change the password from another device, and call "
                "the service desk immediately.",
            ),
        ),
        verify=(
            "The message is gone from the inbox and appears in Reported Items.",
            "The security team confirms receipt if you called them.",
            "No new sign-in prompts arrive after the password change.",
        ),
        troubleshooting=(
            (
                "Reported a genuine message by mistake",
                "Tell the security team it was a false positive; they release it from "
                "quarantine.",
            ),
            (
                "Clicked a link but entered nothing",
                "Close the tab and report the message. No further action is usually needed.",
            ),
            (
                "Opened an attachment",
                "Disconnect from the network and call the service desk; do not try to clean it "
                "yourself.",
            ),
            (
                "A sign-in prompt arrives unexpectedly",
                "Deny it, then change the password and report it: someone already has the "
                "credentials.",
            ),
        ),
        related=("Resetting your work password", "Setting up multi-factor authentication"),
    ),
    Playbook(
        key="updates",
        title="Installing pending Windows updates",
        purpose=(
            "Clear the pending updates that block shutdown, cause repeated restart prompts and "
            "leave the device out of compliance."
        ),
        aliases=("update", "windows update", "patch", "restart", "compliance"),
        applies_to="Managed Windows 10/11 devices",
        time="30-60 minutes",
        prerequisites=(
            "The laptop connected to power and to the corporate network or VPN.",
            "All work saved and closed; a restart is required.",
            "Enough free disk space (Windows Update reports the requirement).",
        ),
        steps=(
            Step(
                "Save and close your work",
                "Updates restart the device without another warning once they are ready.",
            ),
            Step(
                "Open Windows Update",
                "Settings → Windows Update → Check for updates.",
            ),
            Step(
                "Install what is offered",
                "Choose “Download and install”. Feature updates appear separately and can take "
                "an hour.",
                "Leave the laptop plugged in; a battery shutdown mid-update is the usual cause "
                "of a repair loop.",
            ),
            Step(
                "Restart and let it finish",
                "Choose “Restart now” and leave the device alone until the desktop returns. Do "
                "not hold the power button.",
            ),
            Step(
                "Confirm compliance",
                "Return to Windows Update; it should read “You're up to date” with no pending "
                "restart.",
            ),
            Step(
                "Update the applications too",
                "Open the Company Portal and install any pending updates for browsers, Teams and "
                "the PDF reader.",
            ),
        ),
        verify=(
            "Windows Update reports the device is up to date.",
            "No “restart required” banner remains.",
            "The device appears compliant in the management portal (allow 30 minutes).",
        ),
        troubleshooting=(
            (
                "An update fails repeatedly",
                "Free disk space first, then run the Windows Update troubleshooter. Note the "
                "error code for the service desk.",
            ),
            (
                "The device restarts in a loop",
                "Disconnect peripherals and let it complete; if it continues after 30 minutes, "
                "call the service desk.",
            ),
            (
                "Not enough disk space",
                "Empty the Downloads folder and the recycle bin, then retry.",
            ),
            (
                "A driver update breaks a device",
                "Roll the driver back in Device Manager and report it so the update can be "
                "blocked for the model.",
            ),
        ),
        related=("Installing approved software", "Backing up files and restoring a previous version"),
    ),
    Playbook(
        key="shared-mailbox",
        title="Opening and using a shared mailbox",
        purpose=(
            "Work from a team address such as helpdesk@example.com without sharing a "
            "password: add the mailbox to Outlook, send from it, and use its calendar."
        ),
        aliases=(
            "shared mailbox",
            "shared inbox",
            "team mailbox",
            "functional mailbox",
            "send on behalf",
            "send as",
            "mailbox access",
            "shared calendar",
        ),
        applies_to="Outlook for Windows, Outlook on the web and the Outlook mobile app",
        time="10 minutes",
        prerequisites=(
            "Approval from the mailbox owner or their line manager; the service desk "
            "cannot grant access without it.",
            "Your own work account already signed in to Outlook.",
            "The shared mailbox address, for example helpdesk@example.com.",
        ),
        steps=(
            Step(
                "Request access from the owner",
                "Raise the request with the mailbox owner's approval and say which level you "
                "need: read and reply, send on behalf, or send as. The owner approves it; the "
                "service desk applies it.",
                "“Send on behalf” shows “on behalf of” to recipients. “Send as” hides your "
                "name entirely and is only granted for monitored team addresses.",
            ),
            Step(
                "Wait for the permission to apply",
                "Permissions synchronise in 15 to 30 minutes. Restart Outlook after the "
                "request is closed; a mailbox added before the permission lands shows an "
                "error instead of appearing.",
            ),
            Step(
                "Add the mailbox in Outlook for Windows",
                "File → Account Settings → Account Settings → select your account → Change → "
                "More Settings → Advanced → Add, then type the shared address.",
                "Do not use “Add Account”: that asks for a password the shared mailbox does "
                "not have.",
            ),
            Step(
                "Add it on the web and on a phone",
                "In Outlook on the web, right-click your name in the folder pane and choose "
                "“Add shared folder”. On a phone, the mailbox appears automatically once the "
                "desktop or web client has it.",
            ),
            Step(
                "Send from the shared address",
                "Compose a message, open From → Other email address, and choose the shared "
                "address. Replies should leave from it too; set it as the default From while "
                "you are covering the inbox.",
            ),
            Step(
                "Work the inbox without losing messages",
                "Use categories or a shared OneNote page to show who is handling what. "
                "Everyone with access sees the same deletion, so move finished mail to a "
                "team folder instead of deleting it.",
            ),
        ),
        verify=(
            "The shared mailbox appears as a second inbox under your own.",
            "A test message sent from the shared address shows that address as the sender.",
            "A colleague sees the test message in the shared inbox.",
        ),
        troubleshooting=(
            (
                "The mailbox does not appear after adding it",
                "The permission has probably not synced. Restart Outlook, confirm the "
                "request is closed, then allow up to 30 minutes before raising it again.",
            ),
            (
                "Outlook asks for a password",
                "You used Add Account. Remove that entry and add the address through "
                "Advanced → Add so it opens under your own signed-in profile.",
            ),
            (
                "Sending fails or the From list is empty",
                "Send As or Send on Behalf was not granted, or the mailbox is over quota. Use "
                "the level you do have and ask the owner for the rest.",
            ),
            (
                "A message was deleted by mistake",
                "Restore it from Deleted Items, or from Recoverable Items within 30 days. "
                "Everyone with access shares the same recycle bin.",
            ),
        ),
        related=("Setting up work email on desktop and phone", "Signing in with your work account"),
    ),
    Playbook(
        key="mobile-enrolment",
        title="Enrolling a phone or tablet for work",
        purpose=(
            "Enrol a company or personal phone in mobile device management so work mail, "
            "calendar and Teams work, while personal apps stay private and company data can "
            "be removed on its own."
        ),
        aliases=(
            "mobile enrolment",
            "mobile enrollment",
            "device enrolment",
            "device enrollment",
            "phone enrolment",
            "phone enrollment",
            "enrol phone",
            "enroll phone",
            "enrol a phone",
            "enrol my phone",
            "enroll my phone",
            "enrol",
            "enroll",
            "mdm",
            "intune",
            "byod",
            "work profile",
            "work phone",
            "new phone",
        ),
        applies_to="Android and iOS phones and tablets",
        time="15 minutes",
        prerequisites=(
            "Your work account and a second way to approve multi-factor prompts while this "
            "phone is being set up.",
            "A charged phone on Wi-Fi or mobile data.",
            "A screen lock already set: six digits or biometrics.",
            "For a personal phone, agreement that IT can wipe work data only, not the whole "
            "device.",
        ),
        steps=(
            Step(
                "Install the Company Portal",
                "Install “Company Portal” from the App Store or Play Store and check the "
                "publisher is Microsoft Corporation before opening it.",
                "The store listing shows what the app can see. A clone with the same icon "
                "usually has a different publisher and no reviews.",
            ),
            Step(
                "Sign in with your work account",
                "Open the app, choose Sign in, and approve the multi-factor prompt. Read the "
                "management notice before accepting it.",
            ),
            Step(
                "Create the work profile or accept management",
                "On Android, follow the prompt to create a work profile, which keeps work "
                "apps in their own space. On iOS, install the management profile when "
                "Settings offers it.",
                "A work profile is not a second phone: personal apps, photos and accounts "
                "stay outside it.",
            ),
            Step(
                "Set a compliant lock screen",
                "Use a six-digit PIN or biometrics with auto-lock at five minutes or less. "
                "The Company Portal shows the exact policy if your current setting is too "
                "weak.",
            ),
            Step(
                "Let the work apps install",
                "Outlook, Teams, Edge and Authenticator install into the work profile or "
                "appear on the home screen. Open Outlook once and let the first sync finish.",
            ),
            Step(
                "Test it and record the device",
                "Send a test message, join a Teams call and confirm the speaker and "
                "microphone work. For a company phone, add the model and serial to the asset "
                "register.",
            ),
        ),
        verify=(
            "Company Portal lists the device as compliant.",
            "Work mail arrives and a Teams call connects with audio.",
            "Opening a work app asks for the work passcode or biometrics.",
        ),
        troubleshooting=(
            (
                "Company Portal reports the device is not compliant",
                "Open the message and fix the one item named, usually the screen lock or the "
                "OS version, then choose Check compliance.",
            ),
            (
                "Enrolment fails at the profile step",
                "Remove an old work profile or a previous record of this phone first. On iOS "
                "check Settings → General → VPN & Device Management for a stale profile.",
            ),
            (
                "Work apps vanish after a phone update",
                "Reopen Company Portal and sign in; the work profile is paused until the "
                "device checks in again.",
            ),
            (
                "The phone is lost or stolen",
                "Report it immediately so the work profile can be wiped remotely. On Android "
                "personal data stays; on a company-owned iPhone the whole device is erased.",
            ),
        ),
        related=("Setting up multi-factor authentication", "Setting up work email on desktop and phone"),
    ),
    Playbook(
        key="asset-handover",
        title="Handing over and returning loan equipment",
        purpose=(
            "Give a colleague a loan laptop, phone or accessory, or take one back, with a "
            "clear asset trail so the next person gets a known device and nothing goes "
            "missing."
        ),
        aliases=(
            "asset handover",
            "handover",
            "hand over",
            "loan laptop",
            "loan device",
            "borrow laptop",
            "borrow a laptop",
            "asset tag",
            "equipment return",
            "return laptop",
            "return equipment",
            "loan pool",
        ),
        applies_to="Loan pool laptops, phones, docks and accessories",
        time="15 minutes",
        prerequisites=(
            "An approved ticket naming the borrower and the loan dates.",
            "A charged, imaged device from the loan pool, with its asset tag readable.",
            "Access to the asset register and a blank handover form.",
        ),
        steps=(
            Step(
                "Match the request to the right asset",
                "Check the dates, the role and any software or licence the loan needs. Take "
                "the oldest suitable return in the pool so stock rotates instead of ageing "
                "on the shelf.",
                "A loan device is issued to a person, not a desk: record who has it even when "
                "the ticket names a team.",
            ),
            Step(
                "Record the asset tag and its condition",
                "Note the tag, serial, charger, dock and any existing scratches or dents, with "
                "photos, in the register before the device leaves the office.",
                "Photos taken at handover are what settle a damage dispute at return.",
            ),
            Step(
                "Prepare the device for the borrower",
                "Sign out the previous user, wipe or reset their data, apply the loan "
                "profile, confirm encryption and compliance, and install the software named "
                "on the ticket.",
            ),
            Step(
                "Complete the handover form",
                "Record borrower name, asset tag, accessories, return date and their "
                "signature. Give them the return instructions and the service desk number in "
                "writing.",
            ),
            Step(
                "Update the register and the ticket",
                "Set the asset to “On loan”, assign the borrower, link the ticket and set a "
                "return reminder for the working day before it is due.",
            ),
            Step(
                "Process the return",
                "Compare the condition with the handover photos, sign in to confirm it works, "
                "wipe it, and set the register to “Available”. Raise a repair ticket for any "
                "damage before reissuing.",
            ),
        ),
        verify=(
            "The asset register shows the borrower, the loan date and the return date.",
            "The borrower can sign in and reach mail, files and the loan software.",
            "The signed handover form is attached to the ticket.",
        ),
        troubleshooting=(
            (
                "The device will not sign in for the borrower",
                "Check the account and licence status first; a loan device must use the "
                "borrower's own account, never the previous user's cached profile.",
            ),
            (
                "The asset tag is missing or unreadable",
                "Match the serial number in the register before issuing it. If the serial "
                "cannot be read either, quarantine the device instead of guessing.",
            ),
            (
                "Damage is found at return",
                "Compare it with the handover photos, record it on the return form and raise "
                "a repair ticket. Do not put the device back in the loan pool.",
            ),
            (
                "The return date passes with no contact",
                "Send one reminder to the borrower, then escalate to their line manager as "
                "the loan policy requires.",
            ),
        ),
        related=("New starter IT setup", "Signing in with your work account"),
    ),
    Playbook(
        key="teams-meeting",
        title="Joining a Teams meeting with working audio and video",
        purpose=(
            "Join a Teams meeting on time with the right microphone, camera and screen "
            "share, and leave with the follow-ups in the right place."
        ),
        aliases=(
            "teams meeting",
            "teams call",
            "join a meeting",
            "microphone",
            "camera not working",
            "screen share",
            "video call",
            "teams audio",
        ),
        applies_to="Microsoft Teams on Windows, macOS, iOS and Android",
        time="5 minutes",
        prerequisites=(
            "Teams signed in with your work account.",
            "A headset or built-in microphone and camera not held by another app.",
            "A connection that permits calls; some VPN profiles block meeting media.",
        ),
        steps=(
            Step(
                "Join from the calendar",
                "Open Teams → Calendar, find the meeting and choose Join. Join two minutes "
                "early; the lobby waits only if the organiser set one.",
            ),
            Step(
                "Choose audio before you join",
                "On the pre-join screen pick your headset, then speak and watch the input "
                "meter move. Choose computer audio only when you have no headset.",
                "Joining with a phone on speaker in the same room causes echo for everyone "
                "else.",
            ),
            Step(
                "Turn on video when you are ready",
                "Check your framing and background first; blur is fine, but virtual "
                "backgrounds need a supported processor and can soften text.",
            ),
            Step(
                "Share a window, not the whole screen",
                "Choose Share → Window and pick the single window the meeting needs. Share "
                "computer sound only when playing a clip.",
            ),
            Step(
                "Chat and record responsibly",
                "Recording and transcription announce themselves to everyone. Do not record "
                "a customer or HR conversation without consent.",
            ),
            Step(
                "Leave and check the follow-ups",
                "Use Leave unless you are the organiser and the meeting should end for all. "
                "The chat and any shared files remain available in the meeting chat.",
            ),
        ),
        verify=(
            "Your name appears in the participant list with the expected mic and camera "
            "state.",
            "A colleague confirms they can hear you and see the shared window.",
            "No private notification or personal tab is visible while sharing.",
        ),
        troubleshooting=(
            (
                "No one can hear you",
                "Check the microphone selected in Teams, then the operating system privacy "
                "setting. Unplug and replug the headset before rejoining.",
            ),
            (
                "The camera shows a black square",
                "Close other apps that use the camera, open any privacy shutter, then check "
                "the camera in the device settings.",
            ),
            (
                "Everyone hears an echo",
                "All but one person in a shared room should use headphones, or mute the room "
                "device and use a single microphone.",
            ),
            (
                "Screen share shows the wrong display",
                "Stop sharing, move private windows to another desktop, then share the "
                "specific window rather than the screen.",
            ),
        ),
        related=("Connecting to the VPN", "Setting up work email on desktop and phone"),
    ),
    Playbook(
        key="file-access",
        title="Getting access to a team site or shared folder",
        purpose=(
            "Clear an “access denied” message and request the right permission once, whether "
            "the files live in SharePoint or on a network share."
        ),
        aliases=(
            "access denied",
            "sharepoint",
            "team site",
            "folder permissions",
            "file share access",
            "request access",
            "shared folder",
            "permission denied",
        ),
        applies_to="SharePoint team sites, OneDrive shares and network file shares",
        time="10 minutes",
        prerequisites=(
            "The link or path to the site or folder, and the name of the team that owns it.",
            "Your work account, signed in on the corporate network or VPN.",
            "The name of the owner or approver for that site.",
        ),
        steps=(
            Step(
                "Identify which kind of share it is",
                "A SharePoint or OneDrive link and a \\\\fileserver\\ path use different "
                "permission systems. The path in the address bar tells you which team to ask.",
            ),
            Step(
                "Use Request access first",
                "On a SharePoint page, choose Request access and say why you need it and for "
                "how long. The request goes to the site owners with your name attached.",
            ),
            Step(
                "Give the owner what they need to approve",
                "Name the site or folder path, the level you need (read, contribute or "
                "edit) and an end date for temporary access. Approvals are audited.",
            ),
            Step(
                "Check group membership",
                "Access is normally granted through a security group, not to a person. The "
                "service desk adds you to the group; the site owner confirms you should be "
                "in it.",
            ),
            Step(
                "Refresh the sign-in session",
                "Sign out and back in, or wait 15 minutes for the permission to reach your "
                "token. Test in a private window so a cached session cannot mislead you.",
            ),
            Step(
                "Confirm the level works",
                "Open, edit and save a test file to prove contribute access; for read-only, "
                "confirm the edit controls are absent rather than assuming.",
            ),
        ),
        verify=(
            "The site or folder opens without the access-denied page.",
            "A file can be opened and saved at the level you were granted.",
            "The permission entry shows your name, not a colleague's.",
        ),
        troubleshooting=(
            (
                "Still denied after approval",
                "Group membership can take up to 24 hours to apply. Confirm the owner "
                "approved it, then try a private window before escalating.",
            ),
            (
                "You can read but not edit",
                "Only Read was granted. Request Contribute and say what you need to change.",
            ),
            (
                "It works on the web but not in Explorer",
                "Disconnect and remap the drive so Windows requests a fresh token, then "
                "sign out and back in.",
            ),
            (
                "External sharing is blocked",
                "Guest access needs the site owner and IT approval. Do not forward the files "
                "instead; that leaves copies nobody can revoke.",
            ),
        ),
        related=("Connecting to the VPN", "Backing up files and restoring a previous version"),
    ),
)

CATEGORIES = (
    "Accounts & access",
    "Devices & network",
    "Email & collaboration",
    "Files & software",
    "Security & onboarding",
)

_CATEGORIES = {
    "login": "Accounts & access",
    "password-reset": "Accounts & access",
    "mfa": "Accounts & access",
    "file-access": "Accounts & access",
    "vpn": "Devices & network",
    "wifi": "Devices & network",
    "printer": "Devices & network",
    "mobile-enrolment": "Devices & network",
    "asset-handover": "Devices & network",
    "remote-desktop": "Devices & network",
    "updates": "Devices & network",
    "email": "Email & collaboration",
    "shared-mailbox": "Email & collaboration",
    "teams-meeting": "Email & collaboration",
    "software-install": "Files & software",
    "backup": "Files & software",
    "onboarding": "Security & onboarding",
    "phishing": "Security & onboarding",
}

# Ready-to-use briefs for the studio's playbook browser. Each one is tested to
# route back to its own playbook, so a click in the picker can never land on the
# wrong topic.
_BRIEFS = {
    "login": "Create a step-by-step guide for work account login",
    "password-reset": "Write a guide for resetting a forgotten work password",
    "mfa": "Write a guide for setting up multi-factor authentication on a phone",
    "vpn": "Create a guide for connecting to the VPN from home",
    "wifi": "Write a guide for connecting a laptop to staff Wi-Fi",
    "printer": "Write a guide for adding an office printer and clearing the print queue",
    "email": "Write a guide for setting up work email in Outlook",
    "shared-mailbox": "Write a guide for opening and using a shared mailbox in Outlook",
    "mobile-enrolment": "Write a guide for mobile enrolment on a work phone",
    "asset-handover": "Write a guide for asset handover of a loan laptop",
    "software-install": "Write a guide for installing approved software from the Company Portal",
    "backup": "Write a guide for backing up files and restoring a previous version",
    "onboarding": "Create a new starter IT setup guide for the first morning",
    "remote-desktop": "Write a guide for connecting to an office PC with Remote Desktop",
    "teams-meeting": "Write a guide for joining a Teams meeting with working audio and video",
    "file-access": "Write a guide for access denied on a SharePoint team site",
    "phishing": "Write a guide for recognising and reporting a phishing email",
    "updates": "Write a guide for installing a pending Windows update",
}

_BY_KEY = {playbook.key: playbook for playbook in PLAYBOOKS}


def get(key: str) -> Playbook | None:
    return _BY_KEY.get(key)


def match(instruction: str) -> Playbook | None:
    """Pick the playbook whose aliases best match the brief."""
    text = (instruction or "").lower()
    if not text.strip():
        return None
    best: tuple[int, int, Playbook] | None = None
    for playbook in PLAYBOOKS:
        score = 0
        longest = 0
        for alias in playbook.aliases:
            if re.search(rf"\b{re.escape(alias)}\b", text):
                score += len(alias.split())
                longest = max(longest, len(alias))
        if score and (best is None or (score, longest) > (best[0], best[1])):
            best = (score, longest, playbook)
    return best[2] if best else None


def summary() -> list[dict[str, str | int]]:
    return [
        {
            "key": p.key,
            "title": p.title,
            "time": p.time,
            "applies_to": p.applies_to,
            "brief": _BRIEFS[p.key],
            "category": _CATEGORIES[p.key],
            "steps": len(p.steps),
            "first_prerequisite": p.prerequisites[0],
        }
        for p in PLAYBOOKS
    ]


def build_guide(
    playbook: Playbook,
    prefs: Prefs,
    *,
    title: str | None = None,
    detail: str | None = None,
    custom_steps: list[str] | None = None,
) -> list[Block]:
    """Lay one playbook out as a document at the requested detail level.

    Steps written in the brief win over the playbook's own: the brief is the
    instruction, the playbook is only the surrounding structure.
    """
    level = detail or prefs.detail
    blocks: list[Block] = [h(1, title or playbook.title)]
    blocks.append(p(shape(playbook.purpose, prefs)))

    if prefs.include_meta:
        blocks.append(
            kv_table(
                [
                    ("Applies to", playbook.applies_to),
                    ("Audience", f"{prefs.audience} staff"),
                    ("Time needed", playbook.time),
                    ("Owner", "IT Service Desk"),
                ]
            )
        )

    blocks.append(h(2, "Before you begin"))
    blocks.append(bullets([shape(item, prefs) for item in playbook.prerequisites]))

    blocks.append(h(2, "Step-by-step"))
    if custom_steps:
        entries = [(text, "") for text in custom_steps]
    else:
        entries = [(step.title, shape(step.detail, prefs)) for step in playbook.steps]
    if prefs.checklist_steps:
        items = [
            ListItem(content=parse_inline(f"**{title_text}**" + (f" — {detail_text}" if detail_text else "")))
            for title_text, detail_text in entries
        ]
        blocks.append(BulletList(items=items))
    else:
        blocks.append(steps(entries))

    if prefs.audience == "beginner":
        tips = [step.tip for step in playbook.steps if step.tip]
        if tips:
            blocks.append(h(3, "Helpful hints"))
            blocks.append(bullets([hint(tip, prefs) for tip in tips if hint(tip, prefs)]))

    blocks.append(h(2, "Verify it worked"))
    blocks.append(checklist([shape(item, prefs) for item in playbook.verify]))

    if level != "brief" and prefs.include_troubleshooting:
        blocks.append(h(2, "Troubleshooting"))
        rows = [[symptom, shape(fix, prefs)] for symptom, fix in playbook.troubleshooting]
        blocks.append(table(["Symptom", "What to do"], rows))

    if level != "brief" and playbook.related:
        blocks.append(h(2, "Related guides"))
        blocks.append(bullets(list(playbook.related)))

    blocks.append(h(2, "If you need more help"))
    blocks.append(
        p(
            shape(
                f"Contact {playbook.escalation}. Include what you tried and the exact wording "
                "of any error message.",
                prefs,
            )
        )
    )

    if level == "detailed" and prefs.include_document_control:
        blocks.append(h(2, "Document control"))
        blocks.append(
            kv_table(
                [
                    ("Document", title or playbook.title),
                    ("Owner", "IT Service Desk"),
                    ("Review cycle", "Every 6 months, or after a platform change"),
                    ("Scope", playbook.applies_to),
                    ("Feedback", "Reply to the guide's announcement or raise a ticket"),
                ]
            )
        )
    return blocks
