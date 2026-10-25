import type { LegalMove } from "../types";

const simpleHints = new Set([
  "action_has_target_text", "creature_targets", "permanent_targets", "target_restrictions", "choice_schema",
  "face_names", "requires_x_value", "x_value_max",
]);
const simpleChoices = new Set([
  "target_card_id", "selected_face_index", "x_value", "replacement_source_id",
]);

// Undefined defers optional, compound, and other target families to their guards.
export function singleCardTargetReady(
  hints: LegalMove["target_hints"], selectedId: unknown,
): boolean | undefined {
  if (hints?.action_has_target_text !== true
    || !(Array.isArray(hints.creature_targets) || Array.isArray(hints.permanent_targets))
    || Object.keys(hints).some(key => !simpleHints.has(key))) return undefined;
  const schema = hints.choice_schema;
  if (schema !== undefined && (!schema || typeof schema !== "object" || Array.isArray(schema)
    || Object.keys(schema).some(key => !simpleChoices.has(key)))) return undefined;
  return typeof selectedId === "string" && selectedId.length > 0
    && [...(hints.creature_targets ?? []), ...(hints.permanent_targets ?? [])]
      .some(target => target?.id === selectedId);
}
