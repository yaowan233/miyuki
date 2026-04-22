from rosu_pp_py import Beatmap, GameMode, Performance


def get_ss_pp(path: str, mods: int, mode: str) -> float:
    beatmap = Beatmap(path=path)
    convert_mode(beatmap, mode)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    c = Performance(accuracy=100, mods=mods)
    ss_pp_info = c.calculate(beatmap)
    return round(ss_pp_info.pp, 2)

def convert_mode(beatmap: Beatmap, mode: str):
    if mode == "osu":
        mode = GameMode.Osu
    elif mode == "taiko":
        mode = GameMode.Taiko
    elif mode == "catch":
        mode = GameMode.Catch
    elif mode == "mania":
        mode = GameMode.Mania
    else:
        raise ValueError("Invalid mode")
    beatmap.convert(mode)

