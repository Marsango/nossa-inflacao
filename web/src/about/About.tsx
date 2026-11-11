import { Footer } from '../layout/Footer';
import { Header } from '../layout/Header';

function Project() {
  return <section id="projeto" aria-labelledby="project-title"><h2 id="project-title">Sobre o projeto</h2>
    <p>A Nossa inflação é um projeto independente que acompanha preços do varejo brasileiro para ajudar as pessoas a entender as mudanças no custo das compras.</p>
    <p>Preservamos a origem e as condições dos preços. Nossas conclusões devem acompanhar as evidências coletadas.</p>
    <p>O recorte monitorado não representa a inflação nacional. A cobertura depende das lojas, localidades e produtos acompanhados em cada período.</p>
  </section>;
}

function OverviewMethodology() {
  return <>
    <h3>Como calculamos a visão geral</h3>
    <p>Em cada data do gráfico, os pares usam preços observados até aquele dia, dentro do período selecionado e no horário de Brasília. Cada contexto de compra compara seu primeiro preço elegível positivo com o último preço elegível disponível até a data, em pelo menos dois dias distintos. As datas podem ser consecutivas ou não.</p>
    <p>Comparamos o mesmo produto, anúncio, vendedor, loja, localidade e modalidade de compra, com condições e embalagens comparáveis. Cada contexto conta uma vez: coletar mais vezes não dá peso adicional a uma oferta.</p>
    <p>Calculamos a média das variações dos contextos de cada rede varejista, depois das redes de cada produto e, por fim, dos produtos. Os pesos são iguais em cada nível. Não arredondamos as etapas intermediárias. O primeiro ponto é uma referência de 0%, não uma variação medida.</p>
    <h3>Um preço no dia 1 e outro no dia 30</h3>
    <p>Se uma oferta custa R$30 no dia 1 e R$50 no dia 30, ela entra com alta de 66,67% a partir do dia 30. No dia 29, ainda há só uma observação, então ela não participa. Não usamos o preço futuro para preencher os dias anteriores.</p>
    <p>Depois do segundo preço, a comparação histórica permanece incluída. Uma nova observação elegível atualiza o último preço comparado. Se não houver preço novo no dia 31, isso não prova que o preço continuou em R$50: a tabela mantém a data real da última observação usada.</p>
    <h3>Produtos novos, lacunas e cobertura</h3>
    <p>Um produto que aparece pela primeira vez em 01/11 pode participar a partir de 02/11, ou de uma data posterior, assim que tiver um segundo preço elegível no mesmo contexto. Não exigimos um preço no começo do mês.</p>
    <p>Sem nenhum par conhecido até uma data, o resultado fica indisponível. Um par observado depois pode iniciar a comparação, sem alterar os dias anteriores. Não interpolamos nem inventamos preços em dias sem coleta.</p>
    <p>A amostra pode mudar e os pares podem cobrir períodos diferentes. O resultado é uma média de variações observadas até cada data; não é uma variação de um único dia nem um encadeamento de fatores diários. A entrada de novos participantes também pode mudar a média.</p>
    <p>A tabela informa quantos produtos, lojas e contextos participaram, quantos contextos receberam um novo preço elegível naquele dia e os limites das datas realmente comparadas. Esses limites não significam que todos os pares têm as mesmas datas. Contextos distinguem anúncio, vendedor, loja, localidade e modalidade de compra.</p>
  </>;
}

function ProductMethodology() {
  return <>
    <h3>Como calculamos o histórico de um produto</h3>
    <p>A variação de um produto compara ofertas com preços nas duas pontas do intervalo efetivo, no mesmo contexto de compra. Cada rede varejista tem o mesmo peso. Esse painel fica fixo e mantém lacunas intermediárias quando faltam preços.</p>
    <p>O resumo mostra o menor preço disponível na última data com preço. A tabela de lojas mostra as ofertas nas duas pontas, inclusive as excluídas da variação. Sem ofertas comparáveis, o gráfico mostra o menor preço disponível por dia, sem calcular uma variação.</p>
    <p>Frutas e outros produtos genéricos reconhecidos podem reunir anúncios de marcas e pesos diferentes. Comparamos o preço por kg usando o peso declarado e a quantidade de pacotes. Produtos orgânicos, variedades diferentes e versões como Baby ou Turma da Mônica ficam separados. Sem peso conhecido, não calculamos um preço por kg.</p>
  </>;
}

function Methodology() {
  return <section id="metodologia" aria-labelledby="methodology-title"><h2 id="methodology-title">Sobre os dados e a metodologia</h2>
    <p>Monitoramos preços anunciados em lojas online, preservando a origem, a data e as condições de cada observação. Os valores podem variar conforme a localidade, a modalidade de compra e as condições da oferta.</p>
    <p>O intervalo efetivo vai da primeira à última data com preço elegível dentro do período selecionado. Ausência de preço comparável não é preço zero.</p>
    <OverviewMethodology /><ProductMethodology />
    <p>Preços com condições não informadas podem exigir requisitos não verificados. Quando isso ocorre, o histórico apresenta um aviso.</p>
    <h3>Confira a cobertura de cada consulta</h3>
    <p>A cobertura conta separadamente as localidades de cada rede varejista: Pão de Açúcar no Rio de Janeiro/RJ e em São Paulo/SP contam como duas lojas. Produtos e modalidades de compra do mesmo local não multiplicam essa contagem. A última coleta e a metodologia específica aparecem junto ao histórico selecionado. Consulte “Metodologia deste histórico” abaixo do gráfico para conhecer as regras e a versão usadas no cálculo.</p>
  </section>;
}

export function About() {
  return <><Header /><main className="page-width about-page">
    <a className="back-link" href="/">← Explorar preços</a>
    <h1>Sobre a Nossa inflação</h1>
    <p className="about-intro">Entenda o projeto, de onde vêm os preços e o que os dados permitem comparar.</p>
    <Project /><Methodology />
  </main><Footer /></>;
}
