/** Click-to-chat link (wa.me). Nothing is sent by the system: the user's own WhatsApp opens with the text prefilled. */
export function normalizePhone(raw: string): string | null {
  let digits = raw.replace(/[^\d+]/g, "");
  if (digits.startsWith("+")) digits = digits.slice(1);
  else if (digits.startsWith("00")) digits = digits.slice(2);
  else if (digits.startsWith("0")) digits = `92${digits.slice(1)}`; // Pakistani local format 03xx...
  return /^\d{10,15}$/.test(digits) ? digits : null;
}

export function whatsappLink(phone: string, message: string): string | null {
  const number = normalizePhone(phone);
  return number ? `https://wa.me/${number}?text=${encodeURIComponent(message)}` : null;
}
