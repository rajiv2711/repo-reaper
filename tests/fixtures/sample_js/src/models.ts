/** Domain models. */

/** Anything with a display name. */
export interface Named {
  label(): string;
}

/** Base entity with an id. */
export class Entity {
  id: number;

  constructor(id: number) {
    this.id = id;
  }

  describe(): string {
    return `Entity ${this.id}`;
  }
}

/** A user of the system. */
export default class User extends Entity implements Named {
  name: string;

  constructor(id: number, name: string) {
    super(id);
    this.name = name;
  }

  label(): string {
    return this.describe() + ": " + this.name;
  }
}
