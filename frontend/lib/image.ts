/** Resize + compress a picked image in the browser so it fits the server limits (photos <= 512 px / 150 KB). */
export async function fileToDataUrl(file: File, maxDimension = 512): Promise<string> {
  if (!file.type.startsWith("image/")) throw new Error("Choose an image file.");
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Your browser cannot process images.");
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  for (const quality of [0.85, 0.7, 0.55, 0.4]) {
    const dataUrl = canvas.toDataURL("image/jpeg", quality);
    if ((dataUrl.length * 3) / 4 <= 140 * 1024) return dataUrl;
  }
  throw new Error("This image is too detailed to store. Try a smaller picture.");
}
