import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO

def process_ocr_to_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    final_output = []

    # วนลูปอ่านทุก Element ที่อยู่ในระดับบนสุด
    for element in soup.contents:
        if element.name == 'table':
            # แปลง Table เป็น Markdown
            try:
                df = pd.read_html(StringIO(str(element)))[0]
                # ทำความสะอาดข้อมูล: ตัดแถว/คอลัมน์ที่เป็น NaN ทั้งหมด
                df = df.dropna(axis=1, how='all').dropna(axis=0, how='all')
                
                # แปลงเป็น Markdown Table
                md_table = df.to_markdown(index=False)
                final_output.append(f"\n{md_table}\n")
            except Exception:
                continue
        elif element.name is not None:
            # ถ้าเป็นแท็กอื่นๆ เช่น <p>, <div> ให้ดึง text ออกมา
            text = element.get_text().strip()
            if text:
                final_output.append(text)
        else:
            # ถ้าเป็นข้อความธรรมดาที่ไม่มีแท็กหุ้ม
            text = str(element).strip()
            if text:
                final_output.append(text)

    # รวมทุกส่วนเข้าด้วยกันโดยคั่นด้วยบรรทัดใหม่
    return "\n".join(final_output)

# --- ตัวอย่างการใช้งาน ---
raw_ocr_output = """ATAG AISIN TAKAOKA THAILAND GROUP AT-A SINCE 1965 ATEFB SATHI PEP

บริษัท ไอซีน ทาคาโอกะ เอเซีย จำกัด
Page : 1 Of. 1 .....

<table><tr><td>เอกสารของหน่วยงาน :</td><td>มาตรฐาน ( STANDARD )</td><td>เรื่อง : มาตรฐานการติดตั้ง Safety Cover</td><td>ผู้อนุมัติ</td><td>ผู้ตรวจสอบ</td><td>ผู้จัดทำ</td></tr><tr><td></td><td></td><td>เอกสารของหน่วยงาน : หน่วยงานความปลอดภัย และสิ่งแวดล้อม</td><td>ศิริพรธร</td><td>พิมพ์มาลา</td><td>25 พ.ค. 23</td></tr><tr><td></td><td></td><td>หน่วยงานผู้ใช้งาน : หน่วยงานความปลอดภัย และสิ่งแวดล้อม</td><td>GM. Up</td><td>TL/SLS</td><td>SO</td></tr><tr><td colspan="6">ต้องทำการติดตั้ง Safety Cover ตรงส่วนที่มีการหมุน หรือเคลื่อนที่ได้ของเครื่องจักร/อุปกรณ์ ซึ่งเป็นจุดที่มีความเสี่ยงที่พนักงานจะถูกดึง 'ถูกหนีบได้' หรือเป็นจุดที่อาจทำให้เกิดอันตรายต่อพนักงานได้ รวมทั้งจุดที่มีอุณหภูมิสูง หรือเป็นจัดตัว</td></tr></table>

วัตถุประสงค์/หลักการ

<table><tr><td>1. หัวข้อ</td><td>มาตรฐานการติดตั้ง Safety cover</td></tr><tr><td>2. มาตรฐาน</td><td>จุดที่มีความเสี่ยงที่พนักงานจะถูกดึง 'ถูกหนีบได้เช่น ตรงส่วนที่มีการหมุนหรือเคลื่อนที่ได้ของเครื่องจักร/อุปกรณ์ เป็นต้น นั้นต้องทำการติดตั้ง Safety Cover รวมทั้งจุดที่มีอุณหภูมิสูง หรือเป็นจัดตัว</td></tr><tr><td>3. ตัวอย่าง</td><td>1.ได้มีการกำหนดกฎข้อบังคับตัวแต่หัวข้อ A-1-1 เป็นต้นไป เกี่ยวข้องเรื่องวัสดุที่ใช้ ความหนา ขนาด วิธีการติดตั้ง และสี<br/>2. ติดตั้งโครงสร้างเพื่อป้องกันไม่ให้แรงกระแท้ไปในเครื่องจักรได้อย่างง่ายดายในกรณีที่ไม่ทันได้ระวังตัว<br/>3. ให้ออกแบบ cover โดยให้คำนึงถึงงานบริเวณและงานข้อมูลต่างๆ เช่นการ Inspection การ repair เติมน้ำมันและการทำความสะอาด ตามกรณีของจุดที่ไม่มีการรับประกันความปลอดภัย ให้ยกเลิกส่วนที่จำเป็นนี้มาไว้ด้านนอก และกำหนดกฎการใช้งานอย่าง เช่น การตัดต้นกำเนิดพลังงาน<br/>4.ที่ Cover ต้องไม่มีจุดเสียงอาทิเช่นมุมแหลมหรือส่วนใดๆที่ยื่นออกมาที่อาจก่อให้เกิดอันตรายแก่พนักงานได้เมื่อไปสัมผัส<br/>5.ที่ประตู-cover แบบเปิดปิดได้ ต้อง Interlock กับกับการทำงานของอุปกรณ์และเครื่องจักรมือทำการเปิดปิดประตูและ cover<br/>6.แม่มีการกำหนดตามข้อ 1 แล้วแต่ถ้าเป็นตำแหน่งที่อันตรายเป็นพิเศษต้องทาสี Tiger mark ที่ cover<br/>7.ช่องว่างที่ยอมให้เกิดได้ระหว่างอุปกรณ์กับ cover, cover กับ cover, และขนาดช่องว่างของ cover ได้กำหนดโดยระยะของส่วนที่ เคลื่อนที่ได้กับ cover ซึ่งได้สรุปออกมาดังตารางข้างล่างนี้</td></tr><tr><td colspan="2"></td><td>ระยะห่างจาก Cover สิ่งส่วนที่ เคลื่อนที่ได้</td><td>Gap ทรงรี</td><td>Gap สี่เหลี่ยม</td></tr><tr><td></td><td></td><td>น้อยกว่า 100mm</td><td>กว้าง ≤ 10mm</td><td>☐ กว้าง≤10mm</td></tr><tr><td></td><td></td><td>100mm~150mm</td><td>กว้าง ≤20mm</td><td>☐ กว้าง≤20mm</td></tr><tr><td></td><td></td><td>150mm~450mm</td><td>กว้าง≤30mm</td><td>☐ กว้าง≤30mm</td></tr><tr><td></td><td></td><td>≥800mm</td><td>กว้าง≤150mm</td><td>☐ กว้าง≤150mm</td></tr></table>

8. ประตูที่มีอุปกรณ์ SP ติดตั้ง, ตัวเครื่องที่ถูกล้อมรอบด้วย Fence แล้วนั้น เป็นต้น หากไม่ได้ติดตั้ง safety cover เฉพาะสำหรับส่วนที่มี การเคลื่อนที่ก็สามารถทำได้

หมายเหตุ
อ้างอิงมาตรฐานความปลอดภัย อาชีวอนามัย และสิ่งแวดล้อม ATJ No. A-1-0

<table><tr><td>REV</td><td>Date</td><td>Description</td><td>Approved</td><td>Checked</td><td>Prepared</td></tr><tr><td>1</td><td>21-Jul-14</td><td>ยกเลิกข้อความที่สื่อสารกรรม เปลี่ยนแปลงเป็นข้อความที่สื่อสารได้จริง</td><td>ศิริพรธร</td><td>พิมพ์มาลา</td><td>25 พ.ค. 23</td></tr></table>

"""

markdown_result = process_ocr_to_markdown(raw_ocr_output)
print(markdown_result)