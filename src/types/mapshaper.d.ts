declare module "mapshaper" {
  export function applyCommands(commands: string, input: Record<string, string>): Promise<Record<string, string>>;
  const _default: { applyCommands: typeof applyCommands };
  export default _default;
}
