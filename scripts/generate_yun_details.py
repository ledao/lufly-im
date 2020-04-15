
import os
import sqlite3
import json
from typing import *

if __name__ == "__main__":
    pwd = os.path.dirname(__file__)
    db = sqlite3.connect(os.path.join(pwd, "../lufly/sys_data/sys_table.sqlite"))
    cursor = db.cursor()
    q_result = cursor.execute('''
    select 
        a.yun, 
        sum(a.priority) as yun_priority
    from
        (select 
            char, 
            full, 
            priority, 
            
            case substr(full, 1, 2) 
            when 'sh' then 'sh' 
            else 
                case substr(full, 1, 2) 
                when "ch" then "ch" 
                else 
                    case substr(full, 1, 2) 
                    when 'zh' then 'zh' 
                    else 
                        case full
                        when 'ang' then 'a'
                        else 
                            case length(full)
                            when 1 then full
                            else substr(full, 1, 1)
                            end
                        end 
                    end 
                end 
            end as sheng,
            
            case substr(full, 1, 2) 
            when 'sh' then substr(full, 3, 5) 
            else 
                case substr(full, 1, 2) 
                when 'ch' then substr(full, 3, 5) 
                else 
                    case substr(full, 1, 2) 
                    when 'zh' then substr(full, 3, 5) 
                    else 
                        case full
                        when 'ang' then 'ang'
                        else 
                            case length(full) 
                            when 1 then full
                            else 
                                case substr(full, 2, 5)
                                when 've' then 'ue'
                                else substr(full, 2, 5)
                                end
                            end
                        end 
                    end 
                end
            end as yun
        from charphonetable where yun != 'r' and yun != 'n')a
    group by a.yun
    order by yun_priority desc;
    ''')
    ordered_yuns = []
    for e in q_result:
        if e[0] in ['ng', '']: 
            continue
       
        ordered_yuns.append(e[0])

    print(ordered_yuns)

    yun_infos: List[Dict] = []
    for yun in ordered_yuns:
        yun_info = {}
        q_result = cursor.execute(f'''
        select 
            a.sheng,
            sum(a.priority) as sheng_priority
        from
            (select 
                char, 
                full, 
                priority, 
                case substr(full, 1, 2) 
                when 'sh' then 'sh' 
                else 
                    case substr(full, 1, 2) 
                    when "ch" then "ch" 
                    else 
                        case substr(full, 1, 2) 
                        when 'zh' then 'zh' 
                        else 
                            case full
                            when 'ang' then 'a'
                            else 
                                case length(full)
                                when 1 then full
                                else substr(full, 1, 1)
                                end
                            end 
                        end 
                    end 
                end as sheng,
                
                case substr(full, 1, 2) 
                when 'sh' then substr(full, 3, 5) 
                else 
                    case substr(full, 1, 2) 
                    when 'ch' then substr(full, 3, 5) 
                    else 
                        case substr(full, 1, 2) 
                        when 'zh' then substr(full, 3, 5) 
                        else 
                            case full
                            when 'ang' then 'ang'
                            else 
                                case length(full) 
                                when 1 then full
                                else 
                                    case substr(full, 2, 5)
                                    when 've' then 'ue'
                                    else substr(full, 2, 5)
                                    end
                                end
                            end 
                        end 
                    end
                end as yun                   
                from charphonetable where yun != 'r' and yun != 'n')a
        where a.yun = '{yun}'
        group by a.sheng
        order by sheng_priority desc
        ''')
        sheng_infos = []
        for sheng_index, sheng in enumerate(q_result):
            sheng_info = {
                'index': sheng_index,
                'name': sheng[0],
                'num': sheng[1]
            } 
            sheng_infos.append(sheng_info)           
        yun_info['index'] = len(yun_infos)
        yun_info['name'] = yun
        yun_info['shengs'] = sheng_infos
        yun_infos.append(yun_info)
    print(yun_infos)
    with open("yun_details.json", 'w', encoding='utf8') as fout:
        fout.write(json.dumps(yun_infos))

    cursor.close()
    db.close()

    # yun_all_shengs = []
    # for yun_info in yun_infos:
    #     yun_name = yun_info['name']
    #     if len(yun_name) == 1:
    #         continue
    #     yun_shengs = set([e['name'] for e in yun_info['shengs']])
    #     yun_all_shengs.append((yun_name, yun_shengs))
    # print(yun_all_shengs)
    #
    # joint_yuns = {}
    # for i in range(len(yun_all_shengs)):
    #     yun = yun_all_shengs[i][0]
    #     all_shengs = yun_all_shengs[i][1]
    #     can_jointed_yuns = []
    #     for j in range(len(yun_all_shengs)):
    #         if i == j:
    #             continue
    #         else:
    #             other_yun = yun_all_shengs[j][0]
    #             other_all_shengs = yun_all_shengs[j][1]
    #             if len(all_shengs & other_all_shengs) == 0:
    #                 can_jointed_yuns.append(other_yun)
    #     if len(can_jointed_yuns) == 0:
    #         continue
    #     else:
    #         joint_yuns[yun] = can_jointed_yuns
    #
    # for yun in joint_yuns:
    #     all_joint_yuns = joint_yuns[yun]
    #     print(yun, all_joint_yuns)
    #     for i in range(len(all_joint_yuns)):
    #         this_yun = all_joint_yuns[i]
    #
    #         if this_yun in joint_yuns:
    #             for j in range(i + 1, len(all_joint_yuns)):
    #                 if all_joint_yuns[j] in  joint_yuns[this_yun]:
    #                     print(yun, this_yun, all_joint_yuns[j])

    print('done')
