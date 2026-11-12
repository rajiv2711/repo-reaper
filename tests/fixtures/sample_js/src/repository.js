/** Stores users in memory. */
const path = require("node:path");
const { validate } = require("./utils");

/** In-memory user store. */
class UserRepository {
  constructor(dir) {
    this.dir = path.join(dir, "users");
    this.items = new Map();
  }

  /** Save one user; returns the new count. */
  save(user) {
    if (!validate(user.name)) {
      throw new Error("invalid user");
    }
    this.items.set(user.id, user);
    return this.count();
  }

  count() {
    return this.items.size;
  }

  describe() {
    return `${this.count()} users in ${this.dir}`;
  }
}

module.exports = { UserRepository };
