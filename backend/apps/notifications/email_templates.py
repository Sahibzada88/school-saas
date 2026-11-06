"""Plain-text email templates. Values are inserted with str.format on a fixed set of keys, never executed as code."""

TEMPLATES: dict[str, tuple[str, str]] = {
    "welcome": (
        "Welcome to School SaaS",
        "Hello {name},\n\nYour school '{school}' is registered and your free trial has started. Sign in any time:\n{url}\n",
    ),
    "trial_started": (
        "Your free trial has started",
        "Hello {name},\n\nYou have {days} days to explore every feature of School SaaS.\n",
    ),
    "trial_expiring": (
        "Your free trial is ending soon",
        "Hello {name},\n\nYour free trial ends in {days} day(s). Contact platform administration to subscribe and keep full access.\n",
    ),
    "trial_expired": (
        "Your free trial has ended",
        "Hello {name},\n\nYour free trial has ended. Your data is safe and remains readable. Contact platform administration to subscribe.\n",
    ),
    "subscription_expiring": (
        "Your subscription is expiring soon",
        "Hello {name},\n\nYour subscription ends in {days} day(s). Contact platform administration to renew.\n",
    ),
    "subscription_expired": (
        "Your subscription has expired",
        "Hello {name},\n\nYour subscription has expired. Please renew to keep full access. Your data is safe.\n",
    ),
    "payment_confirmation": (
        "Payment received",
        "Hello {name},\n\nWe received {amount}. Your subscription now runs until {until}. Thank you!\n",
    ),
    "fee_reminder": (
        "Fee reminder",
        "Hello {name},\n\nA fee payment is pending for {student}: invoice {invoice}, balance {amount}, due {due}.\n\nIf you have already paid, please ignore this message or contact the school office.\n",
    ),
    "absence_alert": (
        "Absence notice",
        "Hello {name},\n\n{student} was marked absent on {date}. If this is unexpected, please contact the school.\n",
    ),
    "password_reset": (
        "Reset your School SaaS password",
        "Hello {name},\n\nUse the link below to choose a new password. It expires in {minutes} minutes and can be used once.\n\n{link}\n\nIf you did not request this, you can ignore this email.\n",
    ),
}
