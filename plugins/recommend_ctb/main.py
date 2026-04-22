import asyncio
import itertools
from collections import defaultdict
from tqdm import tqdm
from sqlmodel import select, col, distinct, or_, and_

from .models import create_tables, PlayerBP100Catch, NewScore, get_session, get_beatmap_relationship_table, \
    beatmap_relationship_tables
from .osu_network import get_ranking, get_bplist, map_path, download_osu
from .osu_network.mods import calc_mods, mods_dic, mods_to_string
from .osu_network.pp import get_ss_pp


async def crawl_bplist():
    for page in range(120, 201):
        data = await get_ranking("fruits", page)
        for uid in data:
            bplist = await get_bplist(uid, "fruits")
            score = []
            for (bp_position, bp) in enumerate(bplist):
                bp: NewScore
                mod = "".join([i.acronym for i in bp.mods if i.acronym != "CL"])
                mod = calc_mods(mod)
                async with get_session() as session:
                    existing_score = await session.exec(
                        select(PlayerBP100Catch).where(
                            PlayerBP100Catch.player_id == uid,
                            PlayerBP100Catch.beatmap_id == bp.beatmap_id,
                            PlayerBP100Catch.mod == mod
                        )
                    )
                    if not existing_score.first():
                        score.append(PlayerBP100Catch(
                            player_id=uid,
                            beatmap_id=bp.beatmap_id,
                            mod=mod,
                            bp_position=bp_position,
                            pp=bp.pp
                        ))

            # If there are new scores to add, commit them to the database
            if score:
                async with get_session() as session:
                    session.add_all(score)
                    await session.commit()
            # await asyncio.sleep(0.5)
            print(f'{uid} ok')


relationship_cache = defaultdict(lambda: defaultdict(float))


async def main():
    await create_tables()
    # 爬取 bp 列表
    # await crawl_bplist()
    # 计算 beatmap 之间的关系
    async with get_session() as session:
        data = (await session.exec(select(distinct(PlayerBP100Catch.player_id)))).all()
        for uid in tqdm(data):
            bplist = (await session.exec(select(PlayerBP100Catch).where(PlayerBP100Catch.player_id == uid))).all()
            for beatmap1, beatmap2 in itertools.combinations(bplist, 2):
                if beatmap1.beatmap_id > beatmap2.beatmap_id:
                    beatmap1, beatmap2 = beatmap2, beatmap1
                pp_difference = abs(beatmap1.pp - beatmap2.pp)
                bp_difference = abs(beatmap1.bp_position - beatmap2.bp_position)
                relationship_score = (1 / (1 + pp_difference)) + (1 / (1 + bp_difference))
                relationship_cache[(beatmap1.beatmap_id, beatmap1.mod)][
                    (beatmap2.beatmap_id, beatmap2.mod)] += relationship_score
                if relationship_cache[(beatmap1.beatmap_id, beatmap1.mod)][(beatmap2.beatmap_id, beatmap2.mod)] is None:
                    raise Exception
        for beatmap1, dic in tqdm(relationship_cache.items()):
            for beatmap2, score in dic.items():
                table = get_beatmap_relationship_table(beatmap1[0], beatmap2[0])
                session.add(table(relationship_value=score,
                                  beatmap_id1=beatmap1[0],
                                  beatmap_id2=beatmap2[0],
                                  beatmap_mod1=beatmap1[1],
                                  beatmap_mod2=beatmap2[1]))
            await session.flush()
        await session.commit()


async def get_related_map(mapid: int, mods: str):
    res = []
    async with (get_session() as session):
        for table in beatmap_relationship_tables:
            data = await session.exec(select(table).where(table.beatmap_id1 == mapid).where(table.beatmap_mod1 == calc_mods(mods))
                                      .order_by(col(table.relationship_value).desc()).limit(10))
            res.extend((i.beatmap_id2, i.beatmap_mod2, i.relationship_value) for i in data)
    relationship_dict = defaultdict(float)
    for i in res:
        if relationship_dict[(i[0], i[1])] < i[2]:
            relationship_dict[(i[0], i[1])] = i[2]
    res = [(i, j, k) for (i, j), k in relationship_dict.items()]
    res.sort(key=lambda x: x[2], reverse=True)
    return res


async def get_related_maps(uid: int, mods: str):
    bplist = await get_bplist(uid, "fruits")

    # res = []
    # for table in beatmap_relationship_tables:
    #     conditions = [and_(table.beatmap_id1 == i.beatmap_id,
    #                        table.beatmap_mod1 == "".join([j.acronym for j in i.mods if j.acronym != "CL"])) for i in
    #                   bplist]
    #     statement = (
    #         select(table)
    #         .where(or_(*conditions))
    #         .order_by(col(table.relationship_value).desc())
    #         .limit(100)  # 可以调整 limit 为你需要的数量
    #     )
    #     if mods:
    #         statement = statement.where(table.beatmap_mod2 == mods)
    #
    #     async with get_session() as session:
    #         data = await session.exec(statement)
    #         res.extend([(i.beatmap_id2, i.beatmap_mod2, i.relationship_value) for i in data])
    async def fetch_table_data(table):
        async with get_session() as session:
            conditions = [
                and_(
                    table.beatmap_id1 == i.beatmap_id,
                    table.beatmap_mod1 == calc_mods("".join([j.acronym for j in i.mods if j.acronym != "CL"]))
                )
                for i in bplist
            ]

            # 用 or_ 将所有组合条件连接起来
            statement = (
                select(table)
                .where(or_(*conditions))
                .order_by(table.relationship_value.desc())
                .limit(75)  # 限制返回结果数量
            )
            if mods:
                statement = statement.where(table.beatmap_mod2 == calc_mods(mods))

            return await session.exec(statement)

    # 并行获取数据
    results = await asyncio.gather(*[fetch_table_data(table) for table in beatmap_relationship_tables])
    relationship_dict = defaultdict(float)
    for data in results:
        for i in data:
            if relationship_dict[(i.beatmap_id2, i.beatmap_mod2)] < i.relationship_value:
                relationship_dict[(i.beatmap_id2, i.beatmap_mod2)] = i.relationship_value
    res = [(i, j, k) for (i, j), k in relationship_dict.items()]
    res.sort(key=lambda x: x[2], reverse=True)
    distinct_maps = set()
    for i in bplist:
        mod = "".join([j.acronym for j in i.mods if j.acronym != "CL"])
        if (i.beatmap_id, mod) not in distinct_maps:
            distinct_maps.add((i.beatmap_id, mod))
    res = [i for i in res if (i[0], i[1]) not in distinct_maps]
    result = []
    for i in tqdm(res):
        if not (map_path / f"{i[0]}.osu").exists():
            await download_osu(i[0])
        if (map_path / f"{i[0]}.osu").exists():
            skip_outer_loop = False  # 初始化标志变量
            for j in bplist:
                if j.beatmap_id == i[0]:
                    map_mods = calc_mods("".join([k.acronym for k in j.mods]))
                    if (mods_dic["HR"] & map_mods) and not (mods_dic["DT"] & i[1]):
                        skip_outer_loop = True  # 设置标志变量
                        break  # 跳出内层循环
                    if mods_dic["DT"] & map_mods:
                        skip_outer_loop = True  # 设置标志变量
                        break  # 跳出内层循环
                    if (i[1] & ~(mods_dic["HD"])) == (map_mods & ~(mods_dic["HD"])):
                        skip_outer_loop = True  # 设置标志变量
                        break  # 跳出内层循环
            if skip_outer_loop:  # 检查标志变量
                continue  # 跳过外层循环
            pp = get_ss_pp(str(map_path / f"{i[0]}.osu"), i[1], "catch")
            if pp > bplist[-1].pp:
                result.append((i[0], i[1], pp))
    result.sort(key=lambda x: x[2], reverse=True)
    final_result = []
    for i in result:
        final_result.append((i[0], mods_to_string(i[1]), i[2], relationship_dict[(i[0], i[1])]))
    return final_result
    # csv_file_path = f'{uid}.csv'
    #
    # with open(csv_file_path, mode='w', newline='', encoding='gbk') as file:
    #     writer = csv.writer(file)
    #     writer.writerow(['图号', 'mod', 'pp', '刷图容易值（越高越简单）'])
    #     writer.writerows(final_result)


#
if __name__ == '__main__':
    asyncio.run(crawl_bplist())
