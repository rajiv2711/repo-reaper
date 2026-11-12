/** Application service. */
import User from "./models";
import { UserRepository } from "./repository";
import * as utils from "./utils.js";
import { v4 as uuid } from "uuid";

/** Creates and stores users. */
export class UserService {
  repo: UserRepository;

  constructor(dir: string) {
    this.repo = new UserRepository(dir);
  }

  /** Create and save a user. */
  create(name: string): User {
    if (!utils.validate(name)) {
      throw new TypeError("bad name");
    }
    const user = new User(uuid(), utils.clean(name));
    this.log(user.label());
    this.repo.save(user);
    return user;
  }

  log(message: string): void {
    console.log(message, this.repo.describe());
  }
}
