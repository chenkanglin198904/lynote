import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "用法 · LyNote",
  description: "第一次使用 LyNote：目标、界面、入库、学习、决策与空状态含义",
};

const SECTIONS: { id: string; title: string; body: ReactNode }[] = [
  {
    id: "what",
    title: "这是什么",
    body: (
      <>
        <p>LyNote 是个人外脑知识平台，用来筛资料、建带证据的图谱，并在需要时召回、学习和做判断。</p>
        <ol className="mt-3 list-decimal space-y-2 pl-5">
          <li>
            <strong className="text-gold">入库</strong>：从随手记、网页、Markdown、PDF、音频、视频里筛出对当前主题有用的材料。
          </li>
          <li>
            <strong className="text-gold">召回</strong>：按主题找出带出处的主张，而不是搜一篇流畅的空话。
          </li>
          <li>
            <strong className="text-gold">决策</strong>：摊开选项、证据、未知和最强反对意见，你拍板并写回结果。
          </li>
          <li>
            <strong className="text-gold">学习</strong>：用图上的主张讲解 → 追问 → 批改 → 把你的错法挂到正确主张上。
          </li>
        </ol>
        <p className="mt-3">
          质量看拒绝率和能不能点开原文核对，不看摄入量，也不看对话是否流畅。答不上来会写「未知」，这是功能不是故障。
        </p>
      </>
    ),
  },
  {
    id: "not",
    title: "这不是什么",
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li>不是 ChatGPT 套壳，不会在图外编百科标准答案。</li>
        <li>不是笔记全文搜索：没有主张、冲突、决策，就不算本产品。</li>
        <li>不是全量向量仓库：过闸默认拒绝无关内容和营销清单体。</li>
        <li>不是世界模拟、千人社会或多用户云同步。</li>
      </ul>
    ),
  },
  {
    id: "layout",
    title: "第一次打开会看到什么",
    body: (
      <>
        <p>工作台分三栏。首次带有样例主题「图谱还是笔记堆」，以及一份被拒绝的营销清单，用来演示过闸。</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[32rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2 pr-3 font-normal">位置</th>
                <th className="py-2 pr-3 font-normal">名称</th>
                <th className="py-2 font-normal">做什么</th>
              </tr>
            </thead>
            <tbody className="align-top">
              <tr className="border-b border-line">
                <td className="py-2 pr-3 text-gold">左</td>
                <td className="py-2 pr-3">今日桌面</td>
                <td className="py-2">当前主题、随手记、下一步（当前主题、最多三张主卡）；送进来、掌握、偏好默认收起</td>
              </tr>
              <tr className="border-b border-line">
                <td className="py-2 pr-3 text-gold">中</td>
                <td className="py-2 pr-3">导图 + 搜索</td>
                <td className="py-2">总览时主题在上、下一层分排；点进去只留祖先路径，其它兄弟层收起</td>
              </tr>
              <tr>
                <td className="py-2 pr-3 text-gold">右</td>
                <td className="py-2 pr-3">决策简报 / 学习 / 出处</td>
                <td className="py-2">拍板、学知识点、核对原文高亮。学习和决策不在同一条会话里</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-3">
          顶栏那句趋势来自掌握深度/广度。左栏是今日桌面：下一步只列当前主题、最多三张主卡，采集和偏好折在下面。
        </p>
        <p className="mt-3">
          顶栏「学习频道」把庞大主题拆成图上已有的目录：左栏章节摘要，中间导图跟着当前章收起其它兄弟，右侧默认出处、可切问答。有依据的回答可收入当前章节，只连已有主张，不编新知识点。
        </p>
      </>
    ),
  },
  {
    id: "path",
    title: "建议的第一条路径",
    body: (
      <ol className="list-decimal space-y-2 pl-5">
        <li>确认当前主题，或在今日桌面点「新建主题」并切换过去。</li>
        <li>随手记一句话，走「读完这篇 / 会后落地」，或展开「送进来」提交网址 / Markdown / PDF / 音频，送去过闸。</li>
        <li>在「下一步」里拒绝垃圾、接受有用材料。抽取后若出现待挂，点已有概念、当前主题，或原文中的新章名。主张必须能对上原文。</li>
        <li>导图出现节点后，用顶部搜索框搜主题内的词，点结果定位。</li>
        <li>
          右侧「学习」问一个图里有的问题。应看到直答 / 需要时再查 / 依据 / 联想 / 边界。点主张到「出处」核对原文。没有上层主张时不会编原理。
        </li>
        <li>讲解后答一道追问。故意答错一次，图上应多一条误区；再问相邻问题应被带回。</li>
        <li>「决策简报」里选一项并自己写理由，之后补事后结果。这些记录不会进学习会话。</li>
        <li>主题变大后进「学习频道」：先看总目录，再逐章学。问答有依据时可收入当前章节。</li>
      </ol>
    ),
  },
  {
    id: "features",
    title: "功能怎么用",
    body: (
      <div className="space-y-4">
        <Feature title="学习主题" text="过闸、搜索、讲解、简报都锁在当前主题。新建会暂停旧主题。空主题几乎没图，搜索和学习都会未知，应先入库。" />
        <Feature
          title="采集与过闸"
          text="随手记一句话也能入库，原文就是证据。网页、Markdown、PDF、音频、视频在「送进来」里过五道闸再进人审。抽取只写主张，不自动建章。「下一步」待挂只点已有概念、当前主题，或原文里出现的新章名。配置了行业检索时，公开网页只用来对照已有节点，不会建成行业本体，也不会直接当主张。清单体通常被拒。没有出处或对不上原文的 quote 不能变成已确认主张。"
        />
        <Feature
          title="剧本"
          text="今日桌面内置「读完这篇」和「会后落地」，只编排过闸、待审、待挂和可选简报。不是插件、不会自动接受、不会替你拍板。读完这篇之后当天召回偏概念和对立；会后落地之后偏未复盘决策和可行动主张。PDF 和音视频仍走「送进来」。"
        />
        <Feature
          title="图谱与搜索"
          text="总览时主题在上、下一层分排。点节点进入下一级后只留祖先路径，其它兄弟层收起。双击钉住后提问会优先带上这些节点。搜索无命中写未知，不编节点：正在学的内容就入库，换了个说法就在导图里找已有点。"
        />
        <Feature
          title="学习频道"
          text="按图上已有概念拆章，不另编教材大纲。每一章拆成该内化 / 可外置，人可以改分法。左栏摘要、中间导图、右栏出处/问答。讲解后仍会反问。收入当前章节只把已引用主张用 about 挂上，不能发明节点。"
        />
        <Feature
          title="学习"
          text="只引用当前主题图上的主张。直答只放带对立或练过的上层主张；细节在「需要时再查」，不会编原理顶上。点过、挂上、拍板引用过的主张会进入巩固并提高下次召回。联想沿已有边时会标明「这和你已有的 X 是同一类取舍」；没有边就停，点「标成相关」后才写边。其它主题的相关主张单独列出，勾选后才展开。追问只出一道；批改只判对/漏/反。答错把误区挂到正确主张上。"
        />
        <Feature
          title="决策简报"
          text="回答「要不要做 X」。同类问题会带回上次已拍板的决策。采纳必须人手写理由，事后结果也由人写回。记录留在简报页，不和学习混在一起。"
        />
        <Feature
          title="今日、偏好与图谱卫生"
          text="左栏是今日桌面：下一步只列当前主题，顺序待挂 / 待审 / 到期巩固 / 已拍板待复盘；简报草稿只在本周你重算过之后才出现。主卡最多三张。可导出只引用已有 id 的周报。送进来、掌握、偏好默认收起。偏好只影响排序，不能填未知。出处里可把重复概念并入已有概念，或把过时主张标成 deprecated，召回跳过、历史仍在。"
        />
        <Feature
          title="掌握仪表"
          text="深度看主张是否有证据且有对立，广度看概念覆盖。掌握 / 薄弱 / 缺失由练习和图结构判定。没有缺口时先学已有点，而不是继续狂吃信息。"
        />
      </div>
    ),
  },
  {
    id: "empty",
    title: "空状态和「未知」",
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li>还没有主题 → 今日桌面点「新建主题」，否则过闸和召回没有锚。</li>
        <li>主题几乎是空图 → 随手记或展开「送进来」并接受抽取。</li>
        <li>搜索或学习写未知 → 图上没有可引用的点；入库或改搜已有词。</li>
        <li>没有待审材料 → 记下或送新材料过闸。清单体被拒是正常的。</li>
        <li>没有误区档案 → 去「学习」答一道追问。</li>
        <li>没有标出缺口 → 先学已有点，或补对立材料。</li>
        <li>图上还没连上 → 核对后点「标成相关」，不会发明节点。</li>
        <li>还没有可拆的目录 → 先入库抽出主张，在待挂里点已有概念或原文中的新章名；或按已有主张一节一节读。</li>
      </ul>
    ),
  },
  {
    id: "safety",
    title: "安全",
    body: (
      <p>
        这是单人、无登录工具。谁能访问端口，谁就能改你的图谱。本机请用 localhost。不要把未鉴权端口映射到公网，也不要把填好的
        .env 提交进 Git。
      </p>
    ),
  },
];

function Feature({ title, text }: { title: string; text: string }) {
  return (
    <section>
      <h3 className="text-sm font-medium text-gold">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-paper/90">{text}</p>
    </section>
  );
}

export default function GuidePage() {
  return (
    <div className="min-h-screen bg-ink text-paper">
      <header className="flex items-center justify-between border-b border-line px-5 py-3">
        <div className="flex items-baseline gap-3">
          <Link href="/" className="font-serif text-2xl tracking-tight hover:text-gold">
            LyNote
          </Link>
          <p className="text-sm text-muted">用法</p>
        </div>
        <Link href="/" className="text-sm text-gold hover:underline">
          回到工作台
        </Link>
      </header>
      <main className="mx-auto max-w-3xl px-5 py-10">
        <p className="text-sm leading-6 text-muted">
          给第一次使用的人：先看目标和工作台怎么走，再按功能用。完整 Markdown 也在仓库的 GUIDE.md。
        </p>
        <nav className="mt-6 flex flex-wrap gap-2 text-xs">
          {SECTIONS.map((section) => (
            <a key={section.id} href={`#${section.id}`} className="border border-line px-2 py-1 text-muted hover:border-gold hover:text-gold">
              {section.title}
            </a>
          ))}
        </nav>
        <div className="mt-10 space-y-12">
          {SECTIONS.map((section) => (
            <article key={section.id} id={section.id}>
              <h2 className="font-serif text-2xl tracking-tight">{section.title}</h2>
              <div className="mt-4 text-sm leading-7 text-paper/90">{section.body}</div>
            </article>
          ))}
        </div>
      </main>
    </div>
  );
}
