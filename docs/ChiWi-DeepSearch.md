# **Phân tích toàn diện và đánh giá tính khả thi của hệ thống quản lý tài chính cá nhân tự động hóa tích hợp trí tuệ nhân tạo Gemini trên nền tảng Telegram và ứng dụng di động**

Sự chuyển dịch của nền kinh tế toàn cầu sang các phương thức thanh toán không dùng tiền mặt đã tạo ra một khối lượng dữ liệu giao dịch khổng lồ cho mỗi cá nhân. Tuy nhiên, khả năng quản lý và chuyển hóa dữ liệu này thành tri thức tài chính vẫn còn là một thách thức lớn. Các phương pháp ghi chép truyền thống đang dần bộc lộ những hạn chế về mặt thời gian và tính chính xác, thúc đẩy sự ra đời của các giải pháp quản lý tài chính cá nhân (Personal Finance Management \- PFM) thế hệ mới. Trong bối cảnh đó, việc kết hợp khả năng tự động hóa của các hệ điều hành di động với sức mạnh xử lý ngôn ngữ tự nhiên của trí tuệ nhân tạo, đặc biệt là mô hình Gemini của Google, mở ra một hướng đi đầy tiềm năng cho việc xây dựng những trợ lý tài chính cá nhân thông minh, hoạt động theo thời gian thực và có khả năng cá nhân hóa cao.1

## **Sự tiến hóa của hệ sinh thái quản lý tài chính cá nhân và các rào cản hiện tại**

Lịch sử của các ứng dụng PFM có thể được chia thành ba giai đoạn tiến hóa rõ rệt, mỗi giai đoạn giải quyết một bài toán cụ thể nhưng đồng thời cũng tạo ra những thách thức mới. Giai đoạn đầu tiên là kỷ nguyên của sổ tay số, nơi người dùng phải tự nhập liệu mọi khoản chi tiêu vào các ứng dụng như Money Lover đời đầu hoặc Excel. Giai đoạn thứ hai là sự bùng nổ của tính năng đồng bộ hóa ngân hàng qua API (Open Banking), tiêu biểu là Spendee hoặc các dịch vụ liên kết tài khoản của Finsify.4 Giai đoạn thứ ba, hiện đang thành hình, là sự tích hợp sâu của AI tạo sinh để không chỉ ghi chép mà còn phân tích và dự báo hành vi tài chính.6

Tại thị trường Việt Nam, các ứng dụng như Money Lover và Sổ thu chi MISA đã chiếm lĩnh thị phần nhờ khả năng liên kết với hơn 25 ngân hàng nội địa, giúp theo dõi biến động số dư một cách tự động.8 Tuy nhiên, các giải pháp này thường gặp phải hai vấn đề lớn đối với người dùng cá nhân: rủi ro quyền riêng tư khi phải chia sẻ thông tin đăng nhập ngân hàng và tính cứng nhắc trong việc tùy chỉnh các danh mục chi tiêu theo lối sống đặc thù.10 Các ngân hàng số như TNEX hay Timo cũng tích hợp sẵn tính năng quản lý chi tiêu nhưng lại bị giới hạn trong hệ sinh thái của chính ngân hàng đó, khiến người dùng gặp khó khăn khi có nhiều tài khoản tại các định chế tài chính khác nhau.11

Dưới đây là bảng so sánh chi tiết các đặc tính cốt lõi của các ứng dụng PFM phổ biến và giải pháp tự xây dựng tích hợp AI:

| Đặc tính | Ứng dụng PFM Thương mại (Money Lover, Spendee) | Ứng dụng Ngân hàng số (TNEX, Timo) | Giải pháp AI DIY (Telegram \+ Gemini) |
| :---- | :---- | :---- | :---- |
| **Cơ chế nhập liệu** | Liên kết API trực tiếp hoặc quét biên lai AI 4 | Tự động ghi chép giao dịch nội bộ 11 | Tự động đọc thông báo/SMS qua AI 13 |
| **Độ chính xác phân loại** | Dựa trên quy tắc cố định (Rule-based) | Theo danh mục của ngân hàng | Hiểu ngữ cảnh sâu qua LLM 13 |
| **Tính cá nhân hóa** | Báo cáo trực quan cơ bản 10 | Cảnh báo chi tiêu bằng Emoji 11 | Tư vấn chiến lược theo mục tiêu riêng 2 |
| **Quyền sở hữu dữ liệu** | Lưu trữ trên máy chủ nhà phát triển | Lưu trữ tại hệ thống ngân hàng | Hoàn toàn thuộc về người dùng (G-Sheet/SQL) 14 |
| **Chi phí** | Miễn phí hoặc thuê bao hàng tháng 18 | Miễn phí đi kèm dịch vụ ngân hàng | Miễn phí hoặc chi phí API cực thấp 19 |

Sự xuất hiện của mô hình Gemini mang lại khả năng phá vỡ các rào cản này bằng cách cho phép người dùng tự xây dựng một hệ thống "đọc" được mọi thông báo ngân hàng mà không cần quyền truy cập trực tiếp vào tài khoản, từ đó đảm bảo tính riêng tư tối đa mà vẫn giữ được sự tiện lợi của tự động hóa.14

## **Cơ chế kỹ thuật tự động hóa nhập liệu từ thông báo ngân hàng và tin nhắn SMS**

Thách thức lớn nhất trong việc xây dựng một ứng dụng PFM tự động hóa là khâu thu thập dữ liệu giao dịch mà không làm ảnh hưởng đến bảo mật của ứng dụng ngân hàng. Trên các hệ điều hành di động hiện nay, có hai phương thức tiếp cận chính để giải quyết bài toán này, tùy thuộc vào đặc thù của từng nền tảng.

### **Nền tảng Android: Khai thác Notification Listener và các vấn đề về quyền truy cập**

Android cung cấp một kiến trúc linh hoạt hơn so với iOS trong việc cho phép các ứng dụng tương tác với hệ thống thông báo. Cơ chế quan trọng nhất là NotificationListenerService, một dịch vụ chạy nền cho phép ứng dụng đọc toàn bộ nội dung của các thông báo đang hiển thị trên thanh trạng thái.21

Các dự án như NotificationWebhookApp hay NotificationForwarder đã chứng minh tính khả thi của việc sử dụng dịch vụ này để bắt các biến động số dư từ ứng dụng ngân hàng và gửi dữ liệu thô (raw data) đến một địa chỉ Webhook xử lý trung tâm.23 Để đảm bảo độ tin cậy, ứng dụng cần được cấp quyền BIND\_NOTIFICATION\_LISTENER\_SERVICE và thường yêu cầu người dùng tắt các tính năng tối ưu hóa pin hoặc bật chế độ tự khởi chạy (Autostart) trên các dòng máy như Xiaomi, Oppo hay Vivo.24

Một phương thức can thiệp sâu hơn là AccessibilityService. Mặc dù Google khuyến cáo chỉ sử dụng cho mục đích hỗ trợ người khuyết tật, nhưng sức mạnh của dịch vụ này cho phép nó "đọc" được nội dung ngay cả bên trong giao diện của ứng dụng đang mở.26 Tuy nhiên, rủi ro bảo mật từ phương thức này là rất lớn, vì nó có thể bị lạm dụng để đánh cắp mã OTP hoặc thực hiện các hành vi trục lợi tài chính nếu ứng dụng bị cài mã độc.28 Do đó, đối với người dùng cá nhân không chuyên, việc sử dụng các công cụ tự động hóa như Tasker hoặc MacroDroid để bắt thông báo và đẩy lên Telegram thông qua các plugin như AutoNotification được xem là giải pháp an toàn và dễ tiếp cận hơn.30

### **Nền tảng iOS: Tận dụng Shortcuts và rào cản Sandboxing**

iOS áp dụng cơ chế bảo mật nghiêm ngặt theo mô hình "Sandboxing", nơi mỗi ứng dụng hoạt động hoàn toàn độc lập và không thể đọc được thông báo của nhau.33 Điều này khiến việc xây dựng một ứng dụng lắng nghe thông báo trực tiếp trở nên bất khả thi nếu không bẻ khóa hệ điều hành (Jailbreak).

Tuy nhiên, Apple cung cấp một "cửa ngách" thông qua ứng dụng Shortcuts (Phím tắt). Người dùng có thể thiết lập các luồng tự động hóa dựa trên việc nhận tin nhắn SMS từ các đầu số của ngân hàng. Khi một SMS chứa các từ khóa như "biến động số dư" hoặc "số tiền thay đổi" được gửi đến, Shortcuts có thể kích hoạt quy trình trích xuất nội dung và gửi đến một API bên ngoài hoặc ghi trực tiếp vào ứng dụng Numbers/Google Sheets.35 Đối với các giao dịch thực hiện qua Apple Pay, Shortcuts còn cung cấp khả năng can thiệp trực tiếp vào lịch sử thanh toán để ghi lại chi tiết giao dịch một cách tức thời.37

Dưới đây là bảng phân tích kỹ thuật về khả năng can thiệp thông báo trên hai hệ điều hành:

| Tiêu chí | Android (Notification Listener) | iOS (Shortcuts/Automation) |
| :---- | :---- | :---- |
| **Khả năng tự động hoàn toàn** | Rất cao, chạy nền liên tục 24 | Trung bình, phụ thuộc vào SMS/Apple Pay 38 |
| **Độ phức tạp thiết lập** | Thấp (Sử dụng Tasker/MacroDroid) 32 | Cao (Thiết lập nhiều bước trong Shortcuts) 36 |
| **Khả năng đọc thông báo App** | Được hỗ trợ đầy đủ 23 | Không được hỗ trợ (chỉ đọc được SMS) 33 |
| **Tính bảo mật** | Cần thận trọng với quyền Accessibility 29 | Rất cao nhờ cơ chế Sandbox của Apple 33 |
| **Sự can thiệp của người dùng** | Gần như không sau khi thiết lập xong | Có thể yêu cầu xác nhận chạy phím tắt |

Hệ quả của sự khác biệt này là các ứng dụng PFM tự động hóa trên Android thường có trải nghiệm mượt mà hơn cho mọi ngân hàng, trong khi trên iOS, giải pháp tốt nhất là tập trung vào việc xử lý các giao dịch qua SMS hoặc Apple Pay.36

## **Ứng dụng trí tuệ nhân tạo Gemini trong việc cấu trúc hóa dữ liệu và tư vấn tài chính**

Sự đột phá thực sự của ý tưởng này nằm ở việc sử dụng Gemini để thay thế các bộ quy tắc RegEx (biểu thức chính quy) khô cứng. Các thông báo từ ngân hàng Việt Nam thường có định dạng không nhất quán và chứa nhiều từ viết tắt, ví dụ: "VCB: \-500.000VND; 14:30 20/10/24; SD: 10.250.000VND; ND: chuyen tien an trua". Một bộ lọc truyền thống có thể gặp khó khăn khi xử lý các trường hợp nội dung (ND) thay đổi liên tục, nhưng với khả năng hiểu ngôn ngữ tự nhiên, Gemini có thể phân tích chính xác ý định của giao dịch.1

### **Trích xuất thông tin đa phương thức và cấu trúc JSON**

Gemini, đặc biệt là phiên bản 1.5 Flash, được tối ưu hóa cho các tác vụ xử lý nhanh với độ trễ thấp và chi phí tối ưu.19 Hệ thống có thể gửi chuỗi văn bản thông báo hoặc thậm chí là ảnh chụp biên lai (receipt) đến Gemini. AI sẽ không chỉ trích xuất các thông tin cơ bản như số tiền hay thời gian mà còn thực hiện "suy luận ngữ cảnh" để phân loại giao dịch vào các danh mục phù hợp như: Ăn uống, Di chuyển, Mua sắm, hoặc Hóa đơn định kỳ.13

Việc sử dụng khả năng "Structured Output" của Gemini cho phép hệ thống luôn nhận được dữ liệu dưới dạng JSON chuẩn hóa:

![][image1]  
Dữ liệu này sau đó dễ dàng được đồng bộ hóa vào Google Sheets hoặc cơ sở dữ liệu SQLite cục bộ để phục vụ cho việc báo cáo lâu dài.14

### **Xây dựng trợ lý tài chính cá nhân hóa (Personal CFO)**

Vượt ra ngoài việc nhập liệu, Gemini đóng vai trò là một chuyên gia tư vấn chiến lược dựa trên dữ liệu lịch sử và mục tiêu cá nhân của người dùng. Hệ thống có thể được cung cấp các thông tin về thu nhập, nợ nần và các mục tiêu tiết kiệm dài hạn (như mua nhà, mua xe) thông qua các "System Instructions" (chỉ dẫn hệ thống) chi tiết.40

Các loại hình tư vấn mà Gemini có thể thực hiện bao gồm:

1. **Phân tích xu hướng và cảnh báo**: "Bạn đã tiêu vượt mức 20% cho hạng mục giải trí trong tuần này. Nếu tiếp tục tốc độ này, bạn sẽ không thể đạt mục tiêu tiết kiệm 10 triệu trong tháng này".2  
2. **Tối ưu hóa dòng tiền**: So sánh các kịch bản tài chính khác nhau, ví dụ: "Nếu bạn dùng 5 triệu này để trả nợ thẻ tín dụng thay vì mua điện thoại mới, bạn sẽ tiết kiệm được 1,5 triệu tiền lãi trong 6 tháng tới".43  
3. **Lập kế hoạch thuế và đăng ký**: Tự động phát hiện các dịch vụ đăng ký định kỳ (Netflix, Spotify) từ các thông báo giao dịch hàng tháng và gợi ý hủy nếu không sử dụng thường xuyên.43  
4. **Lời khuyên dựa trên nghề nghiệp**: Đối với freelancer hoặc người kinh doanh tự do, AI có thể tư vấn về việc trích lập quỹ dự phòng dựa trên sự biến động của thu nhập hàng tháng.2

Khả năng hỗ trợ tiếng Việt tốt của Gemini giúp các lời khuyên trở nên tự nhiên và dễ tiếp nhận hơn, đồng thời tính năng "Memory" (bộ nhớ ngữ cảnh) giúp AI ghi nhớ các tương tác trước đó để đưa ra phản hồi nhất quán theo thời gian.14

## **Đánh giá tính khả thi: Telegram Bot so với Phát triển Ứng dụng Mobile Riêng lẻ**

Việc lựa chọn nền tảng triển khai là quyết định chiến lược ảnh hưởng trực tiếp đến nỗ lực phát triển, chi phí vận hành và trải nghiệm người dùng cuối, đặc biệt đối với đối tượng "không chuyên".

### **Telegram Bot: Giải pháp tối ưu cho nhu cầu phi thương mại**

Telegram đã trở thành một nền tảng phổ biến cho các ứng dụng mini (Mini Apps) và bot nhờ vào bộ API mạnh mẽ và khả năng tương thích đa nền tảng tuyệt vời.

**Ưu điểm đối với người không chuyên**:

* **Không cần phát triển giao diện (UI)**: Telegram cung cấp sẵn khung chat, các nút bấm điều hướng và khả năng hiển thị dữ liệu linh hoạt. Người dùng có thể tập trung hoàn toàn vào logic xử lý dữ liệu thay vì phải lo lắng về thiết kế bố cục (layout) hay tính tương thích màn hình.46  
* **Triển khai cực nhanh với Low-code**: Các công cụ như n8n hoặc Google Apps Script (GAS) cho phép xây dựng một bot hoàn chỉnh chỉ bằng cách kéo thả hoặc viết một vài đoạn mã đơn giản. Đặc biệt, GAS cho phép vận hành bot hoàn toàn miễn phí trên máy chủ của Google.13  
* **Tính riêng tư và tập trung**: Dữ liệu có thể được đẩy trực tiếp về Google Sheets cá nhân, giúp người dùng toàn quyền kiểm soát thông tin mà không sợ bị rò rỉ cho bên thứ ba.13

**Hạn chế**:

* Phụ thuộc hoàn toàn vào kết nối internet để tương tác với bot.  
* Giao diện bị giới hạn trong khuôn khổ ứng dụng Telegram, khó có thể tạo ra các biểu đồ phức tạp hoặc Dashboard đa chiều như ứng dụng native.48

### **Ứng dụng Mobile riêng (Flutter/React Native): Chuyên nghiệp nhưng đòi hỏi cao**

Việc phát triển một ứng dụng riêng lẻ sử dụng các khung (framework) như Flutter mang lại trải nghiệm người dùng tối ưu hơn nhưng đi kèm với một cái giá đắt về mặt nỗ lực kỹ thuật.50

**Ưu điểm**:

* **Khả năng hoạt động ngoại tuyến (Offline-first)**: Dữ liệu có thể được lưu trữ trong SQLite ngay trên điện thoại, cho phép người dùng xem lại chi tiêu bất cứ lúc nào mà không cần mạng.51  
* **Dashboard trực quan**: Tùy biến hoàn toàn các biểu đồ, đồ thị giúp trực quan hóa tình hình tài chính một cách sinh động.52  
* **Tích hợp phần cứng**: Sử dụng vân tay hoặc khuôn mặt (FaceID) để mở khóa ứng dụng, tăng cường tính bảo mật cho dữ liệu nhạy cảm.4

**Hạn chế đối với người không chuyên**:

* **Nỗ lực bảo trì lớn**: Phải cập nhật ứng dụng thường xuyên để tương thích với các phiên bản Android/iOS mới. Việc đẩy ứng dụng lên App Store hay Play Store cũng yêu cầu các thủ tục và chi phí đăng ký tài khoản nhà phát triển ($99/năm cho Apple).54  
* **Độ phức tạp trong lập trình**: Đòi hỏi kiến thức về quản lý trạng thái (state management), cơ sở dữ liệu di động và quy trình đóng gói ứng dụng.50

Dưới đây là bảng so sánh mức độ nỗ lực phát triển cho hai hướng tiếp cận:

| Tiêu chí | Telegram Bot (via n8n/GAS) | Ứng dụng Mobile (Flutter/Native) |
| :---- | :---- | :---- |
| **Thời gian ra mắt (MVP)** | 1 \- 3 ngày 14 | 4 \- 8 tuần 49 |
| **Kiến thức lập trình** | Cơ bản (JavaScript/Python) | Chuyên sâu (Dart/Widget/API) |
| **Chi phí vận hành** | Gần như bằng 0 14 | $5 \- $20/tháng (Cloud/Stores) |
| **Khả năng tùy biến giao diện** | Trung bình (Template-based) | Cao (Pixel-perfect) |
| **Độ bền vững/Bảo trì** | Thấp, ít lỗi do hệ điều hành | Cao, dễ gặp lỗi phiên bản OS |

Hệ quả phân tích cho thấy, đối với mục đích cá nhân hoặc phi thương mại, việc xây dựng trên **Telegram Bot kết hợp với Google Sheets** là giải pháp có tính khả thi và hiệu quả về mặt chi phí nhất.

## **Kiến trúc hệ thống và Quy trình vận hành đề xuất**

Dựa trên các nghiên cứu về công cụ hiện có, một kiến trúc hệ thống "không máy chủ" (serverless) được đề xuất để tối ưu hóa sự đơn giản cho người không chuyên.

### **Luồng xử lý dữ liệu tự động hóa (Automated Pipeline)**

1. **Thu nhận tín hiệu (Input)**:  
   * Trên Android, ứng dụng MacroDroid hoặc Tasker được thiết lập để "nghe" các thông báo từ danh sách các ứng dụng ngân hàng được chọn. Ngay khi có thông báo, ứng dụng sẽ thực hiện một yêu cầu HTTP POST gửi toàn bộ nội dung thông báo đến Webhook của hệ thống xử lý.24  
   * Trên iOS, người dùng thiết lập Shortcut để bắt SMS từ ngân hàng và thực hiện hành động "Get Contents of URL" để đẩy dữ liệu về máy chủ xử lý.35  
2. **Xử lý và cấu trúc hóa (Processing)**:  
   * Webhook nhận dữ liệu có thể là một Script trên Google Apps Script hoặc một Workflow trên n8n. Tại đây, dữ liệu thô được gửi đến Gemini API kèm theo một Prompt (câu lệnh) hệ thống để yêu cầu bóc tách các trường thông tin cần thiết.13  
   * Gemini phân tích và trả về kết quả định dạng JSON đã được phân loại danh mục.  
3. **Lưu trữ và Phản hồi (Storage & Feedback)**:  
   * Dữ liệu được ghi thành một dòng mới trong Google Sheets. Google Sheets đóng vai trò như cơ sở dữ liệu trung tâm, cho phép người dùng dễ dàng truy cập và chỉnh sửa từ bất kỳ thiết bị nào.13  
   * Đồng thời, một thông báo xác nhận sẽ được gửi ngược lại cho người dùng qua Telegram Bot, hiển thị số tiền đã ghi nhận và danh mục được AI lựa chọn để người dùng kiểm tra nhanh.13

### **Phân tích chi phí sử dụng API Gemini cho cá nhân**

Google cung cấp các gói dịch vụ Gemini với mức giá cực kỳ cạnh tranh cho các nhà phát triển cá nhân, giúp việc duy trì hệ thống trở nên khả thi về mặt tài chính.

| Mô hình | Hạn mức Miễn phí (Free Tier) | Giá Bậc trả phí (Pay-as-you-go) |
| :---- | :---- | :---- |
| **Gemini 2.5 Flash** | 15 RPM (yêu cầu/phút), 1 triệu TPM 19 | $0.075 / 1 triệu tokens đầu vào 20 |
| **Gemini 2.5 Pro** | 2 RPM, 32.000 TPM 19 | $1.25 / 1 triệu tokens đầu vào 20 |

Với nhu cầu cá nhân khoảng 50 giao dịch mỗi ngày, việc sử dụng gói **Gemini 1.5 Flash** hoàn toàn nằm trong hạn mức miễn phí. Ngay cả khi vượt ngưỡng, chi phí hàng tháng cũng sẽ không quá ![][image2] USD, rẻ hơn rất nhiều so với phí thuê bao của các ứng dụng PFM thương mại hiện nay.18

## **Tối ưu hóa giao diện và trải nghiệm cho mục đích cá nhân**

Mặc dù Telegram Bot có những hạn chế nhất định về mặt UI, nhưng người dùng vẫn có thể tạo ra một trải nghiệm chuyên nghiệp thông qua việc áp dụng các nguyên tắc thiết kế tối giản và thông minh.

1. **Sử dụng Rich Formatting và Emoji**: Tận dụng định dạng HTML của Telegram để làm nổi bật các con số quan trọng. Việc sử dụng Emoji không chỉ giúp giao diện sinh động mà còn giúp người dùng nhanh chóng nhận diện danh mục chi tiêu (ví dụ: 🍔 cho thực phẩm, 🚗 cho di chuyển).11  
2. **Tích hợp Inline Buttons cho các thao tác nhanh**: Thay vì yêu cầu người dùng gõ lệnh, bot có thể hiển thị các nút bấm như "Xác nhận", "Sửa danh mục", "Xem báo cáo ngày". Điều này giúp giảm thiểu sai sót và tăng tốc độ tương tác.14  
3. **Tận dụng WebView cho các báo cáo đồ họa**: Telegram cho phép mở các trang web mini (Mini Apps) ngay trong ứng dụng. Người dùng có thể nhúng một biểu đồ Google Sheets hoặc một trang web đơn giản hiển thị Dashboard tài chính để có cái nhìn trực quan hơn mà không cần rời khỏi Telegram.14  
4. **Tương tác bằng giọng nói**: Tích hợp tính năng gửi tin nhắn thoại. Gemini có khả năng chuyển đổi giọng nói thành văn bản và phân tích chi tiêu từ lời nói của người dùng, cực kỳ hữu ích khi đang di chuyển hoặc không tiện gõ phím.13

## **Vấn đề bảo mật, quyền riêng tư và những hệ quả tiềm ẩn**

Khi tự xây dựng một hệ thống tài chính cá nhân, người dùng đồng thời trở thành "giám đốc an ninh" cho chính dữ liệu của mình.

### **Rủi ro và Biện pháp phòng ngừa**

Việc dữ liệu giao dịch đi qua các nền tảng trung gian như Telegram, n8n hay Google Cloud đòi hỏi các biện pháp bảo mật nghiêm ngặt.

* **Lọc thông tin nhạy cảm trước khi xử lý**: Trong mã nguồn Tasker hoặc iOS Shortcuts, người dùng nên thiết lập các bộ lọc để ẩn đi số tài khoản ngân hàng hoặc tên đầy đủ của người gửi/nhận trước khi gửi dữ liệu đến AI. Điều này giúp giảm thiểu rủi ro lộ diện thông tin cá nhân định danh (PII).24  
* **Sử dụng Chế độ ẩn danh của AI**: Khi gọi API Gemini, có thể cấu hình để dữ liệu gửi đi không được sử dụng để huấn luyện mô hình (thông qua các tùy chọn trong Google AI Studio), đảm bảo bí mật tài chính cho người dùng.7  
* **Bảo vệ quyền truy cập Bot**: Sử dụng logic kiểm tra chat\_id hoặc user\_id trong mã nguồn bot. Chỉ những tin nhắn đến từ tài khoản Telegram của chính chủ mới được bot phản hồi và xử lý dữ liệu.14

### **Quyền sở hữu dữ liệu và tính bền vững**

Khác với các ứng dụng thương mại có thể ngừng hoạt động hoặc thay đổi chính sách giá bất cứ lúc nào, giải pháp tự xây dựng dựa trên Google Sheets giúp người dùng có toàn quyền sở hữu dữ liệu của mình mãi mãi. Ngay cả khi Telegram hay Gemini thay đổi, dữ liệu trong Google Sheets vẫn có thể được xuất ra (export) sang các định dạng khác như CSV hay PDF để lưu trữ hoặc chuyển đổi sang hệ thống mới.9