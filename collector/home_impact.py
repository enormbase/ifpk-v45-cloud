"""V49 read-only impact illustration for the APPROVED fictional IFPK home plan.

Only vetted current snapshots drive hypothetical scenarios. This module does NOT
write a customer plan, recalculate formal DSR/stress-DSR, or change Supabase.
The frozen base values were taken from the 2026-11 approved-sheet web snapshot.
"""
from __future__ import annotations

import datetime as dt
import math

PLAN = {
    'source': '2026-11 approved IFPK workbook snapshot, 2046-10 move',
    'baseMonth': '2026-11', 'moveMonth': '2046-10',
    'yearsToMove': 20, 'monthsToSave': 239, 'newMortgageMonths': 360,
    'currentOldPrice': 400_000_000, 'currentNewPrice': 800_000_000,
    'basePriceGrowthPct': -0.233,
    'baseFutureOldPrice': 362_779_952, 'baseFutureNewPrice': 763_747_266,
    'existingLoanBalanceAtMove': 104_117_759,
    'approvedLoanMax': 363_598_263, 'ltvPct': 70,
    'baseMortgageRatePct': 3.70845,
    'baseGrossDepositRatePct': 3.1075,
    'baseNetDepositRatePct': 3.1075 * 0.846,
    'savedFundNow': 20_000_000,
    'approvedOwnCash': 141_486_810,
    'approvedMonthlySave': 345_345,
    'approvedMonthlyLoan': 1_675_319,
    'taxFraction': 0.154,
}


def _month_age(month, now):
    try:
        y, m = map(int, month.split('-'))
        if not (1 <= m <= 12):
            return None
        return (now.year-y)*12 + now.month-m
    except (AttributeError, TypeError, ValueError):
        return None


def payment(principal, rate_pct, months):
    """Monthly end-of-month equal principal+interest payment."""
    if not (0 <= principal < 1e15 and 0 <= rate_pct < 35 and 1 <= months <= 600):
        raise ValueError('신규대출 원금·금리·만기 가정 오류')
    r = rate_pct/1200
    return principal / months if r < 1e-12 else principal * r / (1 - (1+r)**(-months))


def principal_from_payment(monthly_payment, rate_pct, months):
    return monthly_payment / payment(1,rate_pct,months)


def savings_monthly(own_cash_goal, initial, annual_net_pct, months):
    """Monthly effective yield on annual after-tax nominal planning assumption."""
    if not (0 <= annual_net_pct < 35 and months > 0 and 0 <= initial < 1e15):
        raise ValueError('저축금리 또는 기간 오류')
    r = (1 + annual_net_pct/100)**(1/12)-1
    future = initial*(1+r)**months
    gap = max(0,own_cash_goal-future)
    factor = months if r < 1e-12 else math.expm1(months*math.log1p(r))/r
    return gap/factor, future


def scenario(label, g_pct, mortgage_pct, deposit_net_pct, *, approved=False):
    p = PLAN
    if not (-30 < g_pct < 30 and 0 <= mortgage_pct < 30 and 0 <= deposit_net_pct < 30):
        raise ValueError('주택가격·금리 시나리오 범위 오류')
    if approved:
        old_price=p['baseFutureOldPrice']; new_price=p['baseFutureNewPrice']
    else:
        base = 1 + p['basePriceGrowthPct']/100
        now = 1 + g_pct/100
        ratio=(now/base)**p['yearsToMove']
        old_price=round(p['baseFutureOldPrice']*ratio)
        new_price=round(p['baseFutureNewPrice']*ratio)
    net_sale=old_price-p['existingLoanBalanceAtMove']
    # A DSR capacity PROXY. Assume the base's 1,675,319 KRW permitted monthly
    # mortgage payment is unchanged. Other debts/income/stress-rate not recomputed.
    dsr_cap = (p['approvedLoanMax'] if approved else
               principal_from_payment(p['approvedMonthlyLoan'],mortgage_pct,p['newMortgageMonths']))
    ltv_cap=new_price*p['ltvPct']/100
    # Don't borrow more than purchase funding gap or the LTV/DSR proxy cap.
    loan=max(0,min(dsr_cap,ltv_cap,max(0,new_price-net_sale)))
    if approved: loan=p['approvedLoanMax']
    own_cash=max(0,new_price-net_sale-loan)
    save,existing_fv=savings_monthly(own_cash,p['savedFundNow'],deposit_net_pct,p['monthsToSave'])
    repay=payment(loan,mortgage_pct,p['newMortgageMonths'])
    if approved:
        own_cash=p['approvedOwnCash']
        save=float(p['approvedMonthlySave'])
        repay=float(p['approvedMonthlyLoan'])
    return {
        'id':label, 'growthPct':g_pct, 'depositNetPct':deposit_net_pct,
        'mortgagePct':mortgage_pct, 'oldHomeFuture':old_price, 'newHomeFuture':new_price,
        'oldDebtAtMove':p['existingLoanBalanceAtMove'], 'saleNet':net_sale,
        'ltvLimit':round(ltv_cap), 'dsrProxyLimit':round(dsr_cap),
        'newMortgagePrincipal':round(loan),
        'ownCashGoal':round(own_cash), 'existingFundFV':round(existing_fv),
        'monthlySaving':round(save), 'monthlyLoanPayment':round(repay),
        'fixedPrincipalLoanPayment':round(payment(p['approvedLoanMax'],mortgage_pct,p['newMortgageMonths'])),
        'deltaCashGoal':round(own_cash)-p['approvedOwnCash'],
        'deltaMonthlySaving':round(save)-p['approvedMonthlySave'],
        'deltaMonthlyPayment':round(repay)-p['approvedMonthlyLoan'],
    }


def _ok_estimates(estimates, now):
    byid={e.get('id'):e for e in estimates}
    for name in ('DEPOSIT','MORTGAGE'):
        entry=byid.get(name)
        if not entry or entry.get('status')!='ready' or not isinstance(entry.get('value'),(int,float)) or not math.isfinite(entry['value']):
            return None, f'{name}: 공식 월별 통계·평균 계산이 미완료'
        age=_month_age(entry.get('lastMonth'),now)
        if age is None or age<0 or age>4:
            return None, f'{name}: 최신 관측값 경과월이 4개월을 초과하거나 날짜 확인 필요'
    return byid, None


def calculate_home_impact(estimates, now=None):
    """Deterministic snapshot; scenarios are NOT approved-plan updates."""
    now=now or dt.date.today()
    base=scenario('approved',PLAN['basePriceGrowthPct'],PLAN['baseMortgageRatePct'],PLAN['baseNetDepositRatePct'],approved=True)
    response={'status':'pending', 'approvedPlanChanged':False,
        'basis':'2026-11 approved fictional plan; fixed 2046-10 move',
        'assumptions':PLAN.copy(), 'approved':base, 'scenarios':[],
        'scenarioMethod':'LTV 70% cap + approved monthly debt service as DSR proxy; actual DSR/stress DSR not computed',
        'caveats':[
            'R-ONE 지역 아파트 매매가격지수는 개별 기존/신규 주택의 시장가치가 아닙니다.',
            '단일 공식 새 기준 시계열 내 5·10년 과거 변화율은 미래 20년 보장이 아닙니다.',
            'DSR은 기존 계획의 월 상환액을 상한으로 삼은 대리 계산이며 소득·기타부채·스트레스 DSR을 재심사하지 않습니다.',
            '취득세·양도세·중개보수·이사비·추가담보 제한·상환수수료와 미래 규제 변경은 반영하지 않았습니다.',
            '확정계획·구글시트·605개월 현금흐름은 자동 변경되지 않습니다.',
        ], 'vintage':{}}
    byid,error=_ok_estimates(estimates,now)
    if error:
        response['reason']=error
        return response
    deposit=byid['DEPOSIT'];mortgage=byid['MORTGAGE']
    d=float(deposit['value']);m=float(mortgage['value'])
    if not(0<d<20 and 0<m<20):
        response['reason']='금리 추정값 범위 검증 실패'; return response
    response['vintage']={'deposit':deposit['lastMonth'],'mortgage':mortgage['lastMonth']}
    response['scenarios'].append(scenario('rates_only',PLAN['basePriceGrowthPct'],m,d))
    rone=byid.get('HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606')
    if (not rone or rone.get('status')!='ready' or rone.get('indexBaseMonth')!='2026-06'
        or not isinstance(rone.get('rates'),dict)):
        response['status']='partial';response['reason']='R-ONE 새 기준 가격지수의 5년·10년 연속자료 검증 미완료'
        return response
    age=_month_age(rone.get('lastMonth'),now)
    rates=rone['rates'];g5=rates.get('60months');g10=rates.get('120months')
    if (age is None or age < 0 or age > 4 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (g5,g10))):
        response['status']='partial';response['reason']='R-ONE 새 기준 지수의 최신성 또는 장기 CAGR 검증 실패'
        return response
    # Price sensitivity assumes both old and new house growth follows the
    # same *regional* rate, which need not hold for particular properties.
    weighted=(g5+g10)/2
    response['scenarios'] += [scenario('weighted',weighted,m,d),scenario('five_year',g5,m,d),scenario('ten_year',g10,m,d)]
    response['status']='ready';response['vintage']['homePrice']=rone['lastMonth']
    response['method']={'fiveYearCagrPct':g5,'tenYearCagrPct':g10,
                        'weightedGrowthPct':weighted,'weight5':.5,'weight10':.5}
    return response
