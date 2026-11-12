/** Small string helpers. */

/** Trim and lowercase a name. */
export function normalize(name) {
  return name.trim().toLowerCase();
}

/** True when a name is usable. */
export const validate = (name) => {
  if (!name) {
    console.warn("empty name");
    return false;
  }
  return normalize(name).length > 0;
};

export { normalize as clean };
